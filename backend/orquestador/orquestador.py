"""
orquestador.py — Motor central de orquestación multiagente.
Fusiona respuestas de agentes, aplica reglas de correlación
y genera eventos globales explicables.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN, TipoEvento, nivel_mayor
from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag

log = get_logger("orquestador")


# ── Reglas de correlación multiagente ─────────────────────────────────────────
REGLAS_CORRELACION = [
    {
        "id":          "EXPLOSION_INMINENTE",
        "descripcion": "CH4 > 1% + fuego/humo detectado → EXPLOSIÓN INMINENTE",
        "nivel":       NivelRiesgo.EVACUACION,
        "condicion":   lambda g, i, geo: (
            g is not None
            and i is not None
            and g.get("datos_crudos", {}).get("CH4", 0) > 1.0
            and i.get("datos_crudos", {}).get("deteccion") in ("fuego", "humo")
        ),
        "acciones": [
            "🚨🚨 EVACUACIÓN TOTAL — Riesgo EXPLOSIÓN",
            "Cortar TODA la energía eléctrica del nivel",
            "Activar alarma general: 3 pitidos cortos + 1 largo",
            "Llamar 123 — ANM: 57-1-3199099",
        ],
    },
    {
        "id":          "COLAPSO_CON_PERSONAL",
        "descripcion": "Geo crítico + gases críticos + personas presentes",
        "nivel":       NivelRiesgo.EVACUACION,
        "condicion":   lambda g, i, geo: (
            g is not None and geo is not None and i is not None
            and NIVEL_ORDEN.get(NivelRiesgo(geo.get("nivel_riesgo","SEGURO")),0) >= 3
            and NIVEL_ORDEN.get(NivelRiesgo(g.get("nivel_riesgo","SEGURO")),0) >= 3
            and i.get("datos_crudos",{}).get("n_personas",0) > 0
        ),
        "acciones": [
            "🚨 EVACUACIÓN — Colapso estructural + atmósfera contaminada con personal",
            "Activar plan de rescate geomecánico",
            "Notificar Defensa Civil y ANM",
        ],
    },
    {
        "id":          "INCENDIO_ACTIVO",
        "descripcion": "CO > 50 ppm + humo/fuego visual → Incendio activo",
        "nivel":       NivelRiesgo.EMERGENCIA,
        "condicion":   lambda g, i, geo: (
            g is not None and i is not None
            and g.get("datos_crudos",{}).get("CO",0) > 50
            and i.get("datos_crudos",{}).get("deteccion") in ("humo","fuego")
        ),
        "acciones": [
            "Activar Plan de Emergencia contra Incendios Mineros (PECI)",
            "Evacuar con viento a la espalda — no cortar ventilación",
            "Cortar equipos que no sean ATEX",
        ],
    },
    {
        "id":          "SENSOR_INCONSISTENTE",
        "descripcion": "Anomalía sensor gas + imagen normal → posible falla de sensor",
        "nivel":       NivelRiesgo.PRECAUCION,
        "condicion":   lambda g, i, geo: (
            g is not None and i is not None
            and g.get("anomalia",{}).get("tipo_anomalia") == "falla_sensor"
            and i.get("datos_crudos",{}).get("deteccion") == "normal"
        ),
        "acciones": [
            "🔧 INCONSISTENCIA: Sensor reporta falla, imagen normal",
            "Enviar técnico a calibrar sensor",
            "Monitoreo manual hasta calibración",
        ],
    },
    {
        "id":          "DEFICIENCIA_O2_CON_PERSONAL",
        "descripcion": "O2 < 19.5% + personas en zona → riesgo asfixia",
        "nivel":       NivelRiesgo.EMERGENCIA,
        "condicion":   lambda g, i, geo: (
            g is not None and i is not None
            and g.get("datos_crudos",{}).get("O2", 21) < 19.5
            and i.get("datos_crudos",{}).get("n_personas", 0) > 0
        ),
        "acciones": [
            "RIESGO ASFIXIA: Personal en zona con deficiencia de O2",
            "Evacuar usando auto-rescatadores",
            "Maximizar ventilación inmediatamente",
        ],
    },
    {
        "id":          "SISMICIDAD_INDUCIDA",
        "descripcion": "Vibración > 15 mm/s + polvo/derrumbe visual",
        "nivel":       NivelRiesgo.RIESGO_ALTO,
        "condicion":   lambda g, i, geo: (
            geo is not None and i is not None
            and geo.get("datos_crudos",{}).get("vibracion_mms",0) > 15
            and i.get("datos_crudos",{}).get("deteccion") in ("polvo_excesivo","derrumbe_parcial")
        ),
        "acciones": [
            "Activar protocolo sismicidad inducida",
            "Suspender voladuras y maquinaria pesada",
            "Inspección geomecánica urgente",
        ],
    },
]


class Orquestador:
    """Motor central del sistema multiagente."""

    def __init__(self) -> None:
        self._historial: list[dict] = []
        self._estadisticas = {
            "ciclos": 0,
            "evacuaciones": 0,
            "correlaciones": 0,
        }

    def procesar(
        self,
        zona: str,
        resp_gases:    Optional[dict],
        resp_imagen:   Optional[dict],
        resp_geo:      Optional[dict],
        resp_monitor:  Optional[dict],
    ) -> dict:
        """
        Ciclo principal de orquestación:
          1. Fusionar niveles de riesgo
          2. Aplicar reglas de correlación
          3. Consultar RAG global
          4. Construir evento explicable
        """
        self._estadisticas["ciclos"] += 1
        id_evento = str(uuid.uuid4())[:8].upper()
        ts = datetime.utcnow().isoformat()

        # ── 1. Nivel fusionado ────────────────────────────────────────────────
        niveles = []
        for resp in [resp_gases, resp_imagen, resp_geo, resp_monitor]:
            if resp and "nivel_riesgo" in resp:
                try:
                    niveles.append(NivelRiesgo(resp["nivel_riesgo"]))
                except ValueError:
                    pass

        nivel_fusionado = (
            max(niveles, key=lambda n: NIVEL_ORDEN[n])
            if niveles else NivelRiesgo.INFORMATIVO
        )

        # ── 2. Reglas de correlación ──────────────────────────────────────────
        reglas_disparadas = []
        for regla in REGLAS_CORRELACION:
            try:
                if regla["condicion"](resp_gases, resp_imagen, resp_geo):
                    reglas_disparadas.append(regla)
                    nivel_fusionado = nivel_mayor(nivel_fusionado, regla["nivel"])
            except Exception as e:
                log.debug(f"Regla {regla['id']} error: {e}")

        self._estadisticas["correlaciones"] += len(reglas_disparadas)
        if nivel_fusionado == NivelRiesgo.EVACUACION:
            self._estadisticas["evacuaciones"] += 1

        # ── 3. Acciones globales ──────────────────────────────────────────────
        acciones_correlacion = [a for r in reglas_disparadas for a in r["acciones"]]
        acciones_agentes = []
        for resp in [resp_gases, resp_imagen, resp_geo]:
            if resp:
                acciones_agentes.extend(resp.get("acciones", [])[:2])
        # Deduplicar manteniendo orden
        vistos: set[str] = set()
        acciones_globales = []
        for a in acciones_correlacion + acciones_agentes:
            if a not in vistos:
                vistos.add(a)
                acciones_globales.append(a)

        # ── 4. RAG global ─────────────────────────────────────────────────────
        gases_criticos = []
        if resp_gases:
            gases_criticos = [g["gas"] for g in resp_gases.get("gases_criticos", [])]
        deteccion = resp_imagen.get("datos_crudos",{}).get("deteccion","normal") if resp_imagen else "normal"
        riesgo_geo = resp_geo and NIVEL_ORDEN.get(
            NivelRiesgo(resp_geo.get("nivel_riesgo","SEGURO")), 0) >= 2

        docs_rag = rag.consultar_multimodal(gases_criticos, deteccion, bool(riesgo_geo))
        normativa = [d["titulo"] for d in docs_rag[:3]]

        # ── 5. Scores por agente ──────────────────────────────────────────────
        PESOS = {"AGENTE_GASES": 0.35, "AGENTE_IMAGENES": 0.25,
                 "AGENTE_GEOMECANICO": 0.30, "AGENTE_MONITOR": 0.10}
        scores = {}
        for nombre, resp in zip(
            ["AGENTE_GASES","AGENTE_IMAGENES","AGENTE_GEOMECANICO","AGENTE_MONITOR"],
            [resp_gases, resp_imagen, resp_geo, resp_monitor]
        ):
            if resp:
                nv = NIVEL_ORDEN.get(NivelRiesgo(resp.get("nivel_riesgo","SEGURO")), 0)
                scores[nombre] = round(nv / 5 * 10 * PESOS[nombre], 3)
            else:
                scores[nombre] = 0.0

        # ── 6. Predicción de evolución ────────────────────────────────────────
        pred_msg = _predecir_evolucion(nivel_fusionado, resp_gases, resp_geo)

        # ── 7. Explicación global ─────────────────────────────────────────────
        explicacion = _construir_explicacion(
            zona, nivel_fusionado, resp_gases, resp_imagen, resp_geo,
            reglas_disparadas, normativa
        )

        evento = {
            "id_evento":          id_evento,
            "timestamp":          ts,
            "zona":               zona,
            "nivel_global":       nivel_fusionado.value,
            "correlaciones":      [r["descripcion"] for r in reglas_disparadas],
            "acciones_globales":  acciones_globales[:8],
            "normativa":          normativa,
            "gases_criticos":     resp_gases.get("gases_criticos", []) if resp_gases else [],
            "scores_agentes":     scores,
            "prediccion":         pred_msg,
            "explicacion":        explicacion,
            "agentes_disponibles": {
                "gases":        resp_gases is not None,
                "imagenes":     resp_imagen is not None,
                "geomecanico":  resp_geo is not None,
                "monitor":      resp_monitor is not None,
            },
        }
        self._historial.append(evento)
        if len(self._historial) > 1000:
            self._historial.pop(0)

        return evento

    @property
    def historial(self) -> list[dict]:
        return self._historial

    @property
    def estadisticas(self) -> dict:
        return self._estadisticas


def _predecir_evolucion(
    nivel: NivelRiesgo,
    resp_gases: Optional[dict],
    resp_geo:   Optional[dict],
) -> str:
    preds_gases = (resp_gases or {}).get("predicciones", [])
    preds_geo   = (resp_geo   or {}).get("predicciones", [])
    if preds_gases or preds_geo:
        return "⚠️ Tendencia CRECIENTE — nivel crítico esperado en <30 min sin intervención"
    if NIVEL_ORDEN[nivel] >= 3:
        return "📈 Tendencia ESTABLE-ALTA — riesgo persistente sin acciones correctivas"
    if NIVEL_ORDEN[nivel] >= 2:
        return "📊 Tendencia MODERADA — monitoreo intensivo recomendado"
    return "✅ Condiciones dentro de parámetros normales"


def _construir_explicacion(
    zona: str, nivel: NivelRiesgo,
    gases: Optional[dict], imagen: Optional[dict], geo: Optional[dict],
    correlaciones: list[dict], normativa: list[str],
) -> str:
    lineas = [
        f"DIAGNÓSTICO GLOBAL — {zona} | Nivel: {nivel.value}",
        "",
        "ESTADO POR AGENTE:",
    ]
    for nombre, resp in [("Gases", gases), ("Imágenes", imagen), ("Geomecánico", geo)]:
        if resp:
            lineas.append(
                f"  [{nombre}] {resp.get('nivel_riesgo','?'):20s} | "
                f"{resp.get('explicacion','')[:70]}"
            )
        else:
            lineas.append(f"  [{nombre}] OFFLINE — no disponible")

    if correlaciones:
        lineas.append("\nCORRELACIONES DETECTADAS:")
        for c in correlaciones:
            lineas.append(f"  ⚡ {c['descripcion']}")

    if normativa:
        lineas.append("\nNORMATIVA APLICABLE:")
        for n in normativa[:2]:
            lineas.append(f"  📋 {n}")

    return "\n".join(lineas)