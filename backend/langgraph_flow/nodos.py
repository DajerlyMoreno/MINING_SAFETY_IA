"""
nodos.py — Funciones de nodo para el grafo LangGraph (Capa 3).
Cada nodo recibe el EstadoMinerio, realiza su tarea y retorna un dict
con los campos que actualiza. El grafo combina las actualizaciones.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Optional

import httpx

from backend.shared.config import settings
from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN, nivel_mayor
from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag
from backend.llm.llm_engine import llm
from backend.langgraph_flow.estado import EstadoMinerio
from backend.orquestador.orquestador import REGLAS_CORRELACION


def _to_native(obj):
    """
    Convierte recursivamente numpy.float32/64 e int64 a tipos Python nativos.
    Necesario para que el checkpointer msgpack de LangGraph pueda serializar el estado.
    """
    try:
        import numpy as np
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    return obj

log = get_logger("langgraph_nodos")

_http: Optional[httpx.AsyncClient] = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=5.0)
    return _http


async def _post(url: str, payload: dict) -> Optional[dict]:
    try:
        resp = await _client().post(url, json=payload)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning(f"Agente no disponible [{url}]: {e}")
        return None


# ── Nodo 1: Ingesta ────────────────────────────────────────────────────────────

def nodo_ingesta(state: EstadoMinerio) -> dict:
    """Prepara el ciclo: resetea campos transitorios, incrementa iteración."""
    log.debug(f"[GRAFO] ingesta — zona={state['zona']} iter={state.get('iteracion', 0) + 1}")
    return {
        "iteracion": state.get("iteracion", 0) + 1,
        "resp_gases": None,
        "resp_imagen": None,
        "resp_geo": None,
        "resp_monitor": None,
        "nivel_global": "SEGURO",
        "correlaciones": [],
        "acciones_globales": [],
        "docs_rag": [],
        "normativa_titulos": [],
        "diagnostico_llm": "",
        "acciones_llm": [],
        "referencia_llm": "",
        "pronostico_llm": "",
        "requiere_alerta_critica": False,
        "evento_id": "",
    }


# ── Nodo 2: Agentes especializados (llamadas paralelas) ───────────────────────

async def nodo_analizar_agentes(state: EstadoMinerio) -> dict:
    """
    Llama a los 4 agentes especializados en paralelo via asyncio.gather.
    Cada agente puede retornar None si está offline (graceful degradation).
    """
    zona = state["zona"]

    # Llamadas concurrentes a los 4 agentes
    resp_gases, resp_imagen, resp_geo, resp_monitor = await asyncio.gather(
        _post(
            f"{settings.agente_gases.base_url}/analizar",
            {"zona": zona, **state.get("gases", {})},
        ),
        _post(
            f"{settings.agente_imagenes.base_url}/analizar",
            {
                "zona": zona,
                "deteccion":  state.get("imagen", {}).get("deteccion", "normal"),
                "confianza":  state.get("imagen", {}).get("confianza", 0.9),
                "n_personas": state.get("imagen", {}).get("n_personas", 0),
            },
        ),
        _post(
            f"{settings.agente_geomecanico.base_url}/analizar",
            {"zona": zona, **state.get("geo", {})},
        ),
        _post(
            f"{settings.agente_monitor.base_url}/estado",
            {"zona": zona},
        ),
        return_exceptions=False,
    )

    return {
        "resp_gases":   _to_native(resp_gases),
        "resp_imagen":  _to_native(resp_imagen),
        "resp_geo":     _to_native(resp_geo),
        "resp_monitor": _to_native(resp_monitor),
    }


# ── Nodo 3: Correlación multiagente ───────────────────────────────────────────

def nodo_correlacionar(state: EstadoMinerio) -> dict:
    """
    Aplica las 6 reglas de correlación multiagente y calcula el nivel global
    fusionado ponderando las respuestas de gases (35%), imagen (25%), geo (30%).
    """
    g   = state.get("resp_gases")
    i   = state.get("resp_imagen")
    geo = state.get("resp_geo")

    # Fusionar niveles
    niveles = []
    for resp in [g, i, geo]:
        if resp and "nivel_riesgo" in resp:
            try:
                niveles.append(NivelRiesgo(resp["nivel_riesgo"]))
            except ValueError:
                pass

    nivel_fusionado = (
        max(niveles, key=lambda n: NIVEL_ORDEN[n])
        if niveles else NivelRiesgo.INFORMATIVO
    )

    # Aplicar reglas de correlación
    reglas_disparadas = []
    for regla in REGLAS_CORRELACION:
        try:
            if regla["condicion"](g, i, geo):
                reglas_disparadas.append(regla)
                nivel_fusionado = nivel_mayor(nivel_fusionado, regla["nivel"])
        except Exception:
            pass

    # Construir acciones globales (correlación primero, luego agentes)
    acciones: list[str] = []
    for r in reglas_disparadas:
        acciones.extend(r["acciones"])
    for resp in [g, i, geo]:
        if resp:
            acciones.extend(resp.get("acciones", [])[:2])
    seen: set[str] = set()
    acciones_dedup = [a for a in acciones if not (a in seen or seen.add(a))]

    return {
        "nivel_global":           nivel_fusionado.value,
        "correlaciones":          [r["descripcion"] for r in reglas_disparadas],
        "acciones_globales":      acciones_dedup[:8],
        "requiere_alerta_critica": NIVEL_ORDEN[nivel_fusionado] >= 4,
    }


# ── Nodo 4: Consulta RAG ───────────────────────────────────────────────────────

def nodo_consultar_rag(state: EstadoMinerio) -> dict:
    """Recupera fragmentos normativos relevantes según el contexto multimodal."""
    g   = state.get("resp_gases") or {}
    i   = state.get("resp_imagen") or {}
    geo = state.get("resp_geo") or {}

    gases_criticos = [x["gas"] for x in g.get("gases_criticos", [])]
    deteccion      = i.get("datos_crudos", {}).get("deteccion", "normal")
    riesgo_geo     = bool(
        geo and NIVEL_ORDEN.get(
            NivelRiesgo(geo.get("nivel_riesgo", "SEGURO")), 0
        ) >= 2
    )

    docs    = rag.consultar_multimodal(gases_criticos, deteccion, riesgo_geo)
    titulos = [d["titulo"] for d in docs[:3]]

    # _to_native: elimina numpy.float64 del campo 'relevancia' antes de guardar
    # en el checkpoint (msgpack no puede serializar tipos numpy).
    return {"docs_rag": _to_native(docs), "normativa_titulos": titulos}


# ── Nodo 5: Razonamiento LLM ───────────────────────────────────────────────────

async def nodo_razonar_llm(state: EstadoMinerio) -> dict:
    """
    Genera diagnóstico técnico usando Gemini 1.5 Flash + contexto RAG.
    Si el LLM no está disponible, usa fallback de plantilla.
    """
    lecturas = {
        "Gases":       state.get("gases", {}),
        "Geomecánica": state.get("geo", {}),
        "Visual":      state.get("imagen", {}),
    }
    resultado = await llm.razonar_diagnostico(
        zona=state["zona"],
        nivel_riesgo=state["nivel_global"],
        correlaciones=state.get("correlaciones", []),
        lecturas=lecturas,
        normativa_docs=state.get("docs_rag", []),
        historial_niveles=state.get("historial_niveles", []),
    )
    return {
        "diagnostico_llm": resultado.get("diagnostico", ""),
        "acciones_llm":    resultado.get("acciones_llm", []),
        "referencia_llm":  resultado.get("referencia", ""),
        "pronostico_llm":  resultado.get("pronostico", ""),
    }


# ── Nodo 6a: Emitir alerta crítica (EMERGENCIA / EVACUACIÓN) ──────────────────

async def nodo_emitir_alerta(state: EstadoMinerio) -> dict:
    """
    Para niveles >= EMERGENCIA: notifica al bot WhatsApp y registra en historial.
    """
    eid = str(uuid.uuid4())[:8].upper()
    log.warning(f"[ALERTA CRÍTICA] {state['zona']} — {state['nivel_global']} — {eid}")

    # Notificar bot WhatsApp (puerto 8006)
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                "http://127.0.0.1:8006/alertar_interno",
                json={
                    "zona":         state["zona"],
                    "nivel":        state["nivel_global"],
                    "correlaciones": state.get("correlaciones", []),
                    "acciones":     state.get("acciones_globales", [])[:3],
                    "diagnostico":  state.get("diagnostico_llm", ""),
                    "evento_id":    eid,
                },
            )
    except Exception as e:
        log.debug(f"Bot WhatsApp no disponible para alerta: {e}")

    return {
        "evento_id":         eid,
        "historial_niveles": [state["nivel_global"]],
        "historial_eventos": [_resumen(state, eid)],
    }


# ── Nodo 6b: Actualizar gemelo digital (niveles normales/bajos) ────────────────

async def nodo_actualizar_gemelo(state: EstadoMinerio) -> dict:
    """Registra el evento en el gemelo digital sin emitir alertas críticas."""
    eid = str(uuid.uuid4())[:8].upper()
    return {
        "evento_id":         eid,
        "historial_niveles": [state["nivel_global"]],
        "historial_eventos": [_resumen(state, eid)],
    }


# ── Helper ─────────────────────────────────────────────────────────────────────

def _resumen(state: EstadoMinerio, eid: str) -> dict:
    return {
        "id":              eid,
        "ts":              datetime.utcnow().isoformat(),
        "zona":            state["zona"],
        "nivel":           state["nivel_global"],
        "correlaciones":   state.get("correlaciones", []),
        "diagnostico_llm": state.get("diagnostico_llm", ""),
        "normativa":       state.get("normativa_titulos", []),
        "iteracion":       state.get("iteracion", 0),
    }
