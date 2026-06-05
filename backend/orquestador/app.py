"""
app.py — FastAPI del Orquestador Central (Puerto 8000).
Punto de entrada principal del sistema multiagente.
WebSocket para el dashboard React.
Endpoint /orquestar (flujo HTTP clásico).
Endpoint /orquestar_langgraph (flujo LangGraph cíclico con memoria).
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.config import settings, ROOT_DIR
from backend.shared.logger import get_logger
from backend.orquestador.orquestador import Orquestador
from backend.orquestador.communication_manager import CommunicationManager
from backend.rag.rag_engine import rag
from backend.llm.llm_engine import llm
import backend.langgraph_flow.grafo as _grafo_mod

log = get_logger("orquestador_api")

# ── Estado global ─────────────────────────────────────────────────────────────
motor       = Orquestador()
comm: Optional[CommunicationManager] = None
ws_clients: list[WebSocket] = []
_aio_conn   = None   # conexión aiosqlite — se cierra en lifespan teardown


@asynccontextmanager
async def lifespan(app: FastAPI):
    global comm, _aio_conn
    log.info("=== Iniciando Orquestador Central ===")
    rag.inicializar()
    llm.inicializar()

    # ── Persistencia SQLite async para LangGraph ──────────────────────────────
    # Intenta AsyncSqliteSaver; si falta la dependencia cae a MemorySaver.
    try:
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from pathlib import Path

        db_path = ROOT_DIR / "data" / "langgraph_checkpoints.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        _aio_conn = await aiosqlite.connect(str(db_path))
        checkpointer = AsyncSqliteSaver(_aio_conn)
        _grafo_mod.grafo_mineria = _grafo_mod.construir_grafo(checkpointer)
        log.info(f"LangGraph: AsyncSqliteSaver activo → {db_path}")
    except Exception as e:
        log.warning(
            f"AsyncSqliteSaver no disponible ({e}). "
            "LangGraph usa MemorySaver (sin persistencia en disco). "
            "Instala con: pip install langgraph-checkpoint-sqlite aiosqlite"
        )
        # grafo_mineria ya tiene MemorySaver por defecto desde grafo.py

    comm = CommunicationManager()
    await comm.__aenter__()
    log.info(f"Orquestador listo en :8000 | LLM: {'Gemini' if llm.operativo else 'Fallback'}")
    yield
    await comm.__aexit__(None, None, None)
    if _aio_conn:
        await _aio_conn.close()
        log.info("Conexión SQLite LangGraph cerrada.")
    log.info("=== Orquestador detenido ===")


app = FastAPI(
    title="🧠 Orquestador Multiagente — UPTC 2026",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class OrquestarRequest(BaseModel):
    zona:    str = Field(example="Frente_A_Sogamoso")
    gases:   dict = Field(example={"CH4":0.8,"CO":15,"CO2":0.2,"O2":20.8,"H2S":0.3})
    imagen:  dict = Field(example={"deteccion":"normal","confianza":0.95,"n_personas":3})
    geo:     dict = Field(example={"deformacion_mm":1.5,"vibracion_mms":4.0,
                                    "presion_kpa":35,"convergencia_mm":2.0,
                                    "indice_estabilidad":0.85})


class ConsultaRAGRequest(BaseModel):
    query:     str = Field(example="Qué hacer si CH4 supera 2%")
    k:         int = Field(default=3, ge=1, le=5)
    categoria: Optional[str] = None
    con_llm:   bool = Field(
        default=True,
        description="Si True, usa Gemini para generar respuesta a partir de los fragmentos recuperados."
    )


class ConsultaLLMRequest(BaseModel):
    consulta: str = Field(example="¿Qué significa CH4 al 1.2% y qué debo hacer?")


class LangGraphRequest(BaseModel):
    zona:   str  = Field(example="Frente_A_Sogamoso")
    gases:  dict = Field(example={"CH4": 0.8, "CO": 15, "CO2": 0.2, "O2": 20.8, "H2S": 0.3})
    imagen: dict = Field(example={"deteccion": "normal", "confianza": 0.95, "n_personas": 3})
    geo:    dict = Field(example={
        "deformacion_mm": 1.5, "vibracion_mms": 4.0,
        "presion_kpa": 35, "convergencia_mm": 2.0, "indice_estabilidad": 0.85
    })


# ── WebSocket: broadcasting al dashboard ──────────────────────────────────────
async def broadcast(mensaje: dict) -> None:
    """Envía un evento a todos los clientes WebSocket conectados."""
    desconectados = []
    for ws in ws_clients:
        try:
            await ws.send_json(mensaje)
        except Exception:
            desconectados.append(ws)
    for ws in desconectados:
        ws_clients.remove(ws)


@app.websocket("/ws/eventos")
async def websocket_eventos(websocket: WebSocket):
    await websocket.accept()
    ws_clients.append(websocket)
    log.info(f"WebSocket conectado. Clientes activos: {len(ws_clients)}")
    try:
        while True:
            await websocket.receive_text()  # mantener viva la conexión
    except WebSocketDisconnect:
        ws_clients.remove(websocket)
        log.info(f"WebSocket desconectado. Clientes activos: {len(ws_clients)}")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    estados = comm.obtener_estados() if comm else {}
    return {
        "sistema":    "ORQUESTADOR_MULTIAGENTE",
        "estado":     "ACTIVO",
        "timestamp":  datetime.utcnow().isoformat(),
        "agentes":    estados,
        "ws_clientes": len(ws_clients),
    }


@app.post("/orquestar")
async def orquestar(req: OrquestarRequest):
    """
    Endpoint principal: recibe datos de todos los sensores,
    consulta agentes especializados y retorna evento global.
    """
    if req.zona not in settings.zonas:
        raise HTTPException(400, f"Zona no soportada: {req.zona}")

    # Solo agente de gases activo; imagen y geo desactivados
    resp_gases  = await comm.analizar_gases(req.zona, req.gases)
    resp_imagen = None
    resp_geo    = None

    # Monitor: estado actual de agentes
    resp_monitor = {
        "nivel_riesgo": "SEGURO",
        "estado_agentes": comm.obtener_estados(),
        "latencias": comm.obtener_latencias_promedio(),
    }

    # Orquestar
    evento = motor.procesar(req.zona, resp_gases, resp_imagen, resp_geo, resp_monitor)

    # Incluir lecturas crudas de gases para el dashboard en tiempo real
    evento["datos_gases"] = req.gases

    # ── LLM: razonamiento contextual sobre el evento ──────────────────────────
    # Se llama en TODOS los eventos, no solo en LangGraph.
    # En modo fallback (sin GEMINI_API_KEY) retorna en <1 ms con plantilla.
    try:
        gases_criticos_nombres = [g["gas"] for g in (resp_gases or {}).get("gases_criticos", [])]
        deteccion_visual       = (req.imagen or {}).get("deteccion", "normal")
        riesgo_geo             = bool(
            resp_geo and
            evento.get("nivel_global") not in ("SEGURO", "INFORMATIVO")
        )
        docs_rag = rag.consultar_multimodal(gases_criticos_nombres, deteccion_visual, riesgo_geo)

        llm_result = await asyncio.wait_for(
            llm.razonar_diagnostico(
                zona=req.zona,
                nivel_riesgo=evento["nivel_global"],
                correlaciones=evento.get("correlaciones", []),
                lecturas={"gases": req.gases, "geo": req.geo},
                normativa_docs=docs_rag,
                historial_niveles=[
                    e["nivel_global"] for e in motor.historial[-6:]
                    if e.get("zona") == req.zona
                ],
            ),
            timeout=8.0,
        )
        evento["diagnostico_llm"] = llm_result.get("diagnostico", "")
        evento["acciones_llm"]    = llm_result.get("acciones_llm", [])
        evento["referencia_llm"]  = llm_result.get("referencia", "")
        evento["pronostico_llm"]  = llm_result.get("pronostico", "")
    except asyncio.TimeoutError:
        log.warning("LLM timeout en /orquestar — evento sin diagnóstico LLM")
    except Exception as e:
        log.debug(f"LLM no disponible en /orquestar: {e}")

    # Broadcast WebSocket al dashboard
    await broadcast({"tipo": "EVENTO_GLOBAL", "datos": evento})

    return evento


@app.get("/estado")
async def estado():
    stats = motor.estadisticas
    return {
        "estadisticas":    stats,
        "agentes":         comm.obtener_estados(),
        "latencias_ms":    comm.obtener_latencias_promedio(),
        "ws_conectados":   len(ws_clients),
        "historial_count": len(motor.historial),
    }


@app.get("/historial")
async def historial(n: int = 20, zona: Optional[str] = None):
    evts = motor.historial
    if zona:
        evts = [e for e in evts if e["zona"] == zona]
    return {"total": len(evts), "eventos": evts[-n:]}


@app.post("/rag/consultar")
async def consultar_rag(req: ConsultaRAGRequest):
    """
    Consulta el corpus normativo (Decreto 1886/2015).
    Con con_llm=True (defecto): recupera fragmentos con FAISS y genera
    una respuesta en lenguaje natural usando Gemini.
    Con con_llm=False: devuelve solo los fragmentos recuperados (modo legado).
    """
    if req.con_llm:
        resultado = await rag.consultar_con_llm(
            consulta=req.query,
            k=req.k,
            categoria=req.categoria,
            estado_actual=f"Sistema activo — {len(ws_clients)} clientes conectados",
        )
        return {
            "query":      req.query,
            "respuesta":  resultado["respuesta"],
            "fuentes":    resultado["fuentes"],
            "llm_activo": resultado["llm_activo"],
            "docs_rag":   resultado["docs_rag"],
        }
    # Modo legado: solo fragmentos crudos
    resultados = rag.consultar(req.query, k=req.k, categoria=req.categoria)
    return {"query": req.query, "resultados": resultados}


@app.get("/llm/estado")
async def estado_llm():
    """Diagnóstico del motor LLM: si está operativo, error actual, modelo usado."""
    return {
        **llm.estado,
        "nota": (
            "Operativo=True significa que el cliente Gemini fue creado. "
            "Si las respuestas son fallback, revisa ultimo_error — "
            "429=cuota agotada, 403=clave inválida."
        ),
    }


@app.post("/llm/consultar")
async def consultar_llm(req: ConsultaLLMRequest):
    """
    Responde una consulta en lenguaje natural usando LLM + RAG.
    Mismo pipeline que el bot WhatsApp, accesible desde el dashboard.
    """
    docs = rag.consultar(req.consulta, k=3)
    from backend.whatsapp.bot import ESTADO_SISTEMA
    estado_txt = f"Zona: {ESTADO_SISTEMA['zona']}, Nivel: {ESTADO_SISTEMA['nivel']}"
    respuesta = await llm.responder_consulta(req.consulta, docs, estado_txt)
    return {
        "consulta":   req.consulta,
        "respuesta":  respuesta,
        "llm_activo": llm.operativo,
        "docs_rag":   len(docs),
    }


@app.post(
    "/recibir_analisis",
    summary="Recibe análisis ya procesados de los agentes (flujo correcto)",
    description=(
        "Los agentes procesan sus sensores de forma independiente y envían "
        "su análisis aquí. El orquestador correlaciona los resultados. "
        "Complementa /orquestar que recibe datos crudos."
    ),
)
async def recibir_analisis(req: dict):
    """
    Flujo correcto: Agentes ya procesaron sus sensores → Orquestador correlaciona.
    """
    zona            = req.get("zona", settings.simulacion_zona_default)
    analisis_gases  = req.get("analisis_gases")  or {}
    analisis_geo    = req.get("analisis_geo")    or {}
    analisis_imagen = req.get("analisis_imagen") or {}

    resp_monitor = {
        "nivel_riesgo":  "SEGURO",
        "estado_agentes": comm.obtener_estados() if comm else {},
    }

    evento = motor.procesar(
        zona,
        resp_gases   = analisis_gases  or None,
        resp_imagen  = analisis_imagen or None,
        resp_geo     = analisis_geo    or None,
        resp_monitor = resp_monitor,
    )
    evento["datos_gases"] = analisis_gases.get("datos_crudos", {})
    evento["flujo"]       = "agentes_independientes"

    await broadcast({"tipo": "EVENTO_GLOBAL", "datos": evento})
    return evento


@app.post("/orquestar_langgraph")
async def orquestar_langgraph(req: LangGraphRequest):
    """
    Endpoint LangGraph: ejecuta el flujo cíclico con memoria persistente.
    Es el endpoint principal del simulador — reemplaza /orquestar.
    Usa thread_id=zona para mantener el historial acumulativo por frente.
    """
    if req.zona not in settings.zonas:
        raise HTTPException(400, f"Zona no soportada: {req.zona}")

    estado_inicial = {
        "zona":              req.zona,
        "gases":             req.gases,
        "imagen":            req.imagen,
        "geo":               req.geo,
        "historial_niveles": [],
        "historial_eventos": [],
        "iteracion":         0,
    }

    config = {"configurable": {"thread_id": req.zona}}
    try:
        resultado = await _grafo_mod.grafo_mineria.ainvoke(estado_inicial, config=config)
    except Exception as e:
        log.error(f"Error en grafo LangGraph: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Error en grafo LangGraph: {type(e).__name__}: {str(e)}")

    # Extraer gases_criticos del análisis del agente de gases (si estuvo disponible)
    resp_gases = resultado.get("resp_gases") or {}
    gases_criticos = resp_gases.get("gases_criticos", [])

    # Construir predicción de evolución desde el pronóstico LLM o nivel
    nivel_str    = resultado.get("nivel_global", "SEGURO")
    pronostico   = resultado.get("pronostico_llm", "")
    if not pronostico:
        from backend.shared.enums import NIVEL_ORDEN, NivelRiesgo
        try:
            orden = NIVEL_ORDEN[NivelRiesgo(nivel_str)]
        except (ValueError, KeyError):
            orden = 0
        if orden >= 4:
            pronostico = "⚠️ Tendencia CRÍTICA — intervención inmediata requerida"
        elif orden >= 3:
            pronostico = "📈 Tendencia CRECIENTE — monitoreo intensivo recomendado"
        elif orden >= 2:
            pronostico = "📊 Tendencia MODERADA — vigilancia aumentada"
        else:
            pronostico = "✅ Condiciones dentro de parámetros normales"

    evento = {
        # Campos base (compatibles con el dashboard y AlertPanel)
        "id_evento":          resultado.get("evento_id", ""),
        "timestamp":          datetime.utcnow().isoformat(),
        "zona":               resultado["zona"],
        "nivel_global":       nivel_str,
        "correlaciones":      resultado.get("correlaciones", []),
        "acciones_globales":  resultado.get("acciones_globales", []),
        "normativa":          resultado.get("normativa_titulos", []),
        "gases_criticos":     gases_criticos,
        "prediccion":         pronostico,
        "explicacion":        resultado.get("diagnostico_llm", ""),
        # Campos LLM
        "diagnostico_llm":    resultado.get("diagnostico_llm", ""),
        "acciones_llm":       resultado.get("acciones_llm", []),
        "referencia_llm":     resultado.get("referencia_llm", ""),
        "pronostico_llm":     resultado.get("pronostico_llm", ""),
        # Metadatos LangGraph
        "iteracion":          resultado.get("iteracion", 0),
        "historial_len":      len(resultado.get("historial_niveles", [])),
        "motor":              "LangGraph",
        # Lecturas crudas para el dashboard de gases
        "datos_gases":        req.gases,
        "agentes_disponibles": {
            "gases":       resp_gases.get("nivel_riesgo") is not None,
            "imagenes":    resultado.get("resp_imagen") is not None,
            "geomecanico": resultado.get("resp_geo") is not None,
            "monitor":     resultado.get("resp_monitor") is not None,
        },
    }

    # También persiste en el historial clásico del orquestador para /historial
    motor.historial.append(evento)
    if len(motor.historial) > 1000:
        motor.historial.pop(0)

    # Broadcast como EVENTO_GLOBAL para que el WebSocket lo reciba igual que /orquestar
    await broadcast({"tipo": "EVENTO_GLOBAL", "datos": evento})
    return evento


@app.get("/langgraph/historial/{zona}")
async def historial_langgraph(zona: str):
    """
    Retorna el historial acumulado del grafo para una zona.
    El MemorySaver guarda el estado entre ciclos de monitoreo.
    """
    config = {"configurable": {"thread_id": zona}}
    try:
        state = await _grafo_mod.grafo_mineria.aget_state(config)
        valores = state.values if state else {}
        return {
            "zona":              zona,
            "iteracion":         valores.get("iteracion", 0),
            "historial_niveles": valores.get("historial_niveles", []),
            "historial_eventos": valores.get("historial_eventos", []),
        }
    except Exception as e:
        return {"zona": zona, "error": str(e), "historial_niveles": []}


@app.post("/reset")
async def reset_orquestador():
    """Reinicia el historial del orquestador y la memoria de LangGraph.
    - Borra checkpoints SQLite (AsyncSqliteSaver) o reconstruye con MemorySaver.
    - Limpia el historial de eventos en memoria del motor.
    """
    global _aio_conn

    # 1. Limpiar historial de eventos del motor
    motor.historial.clear()

    # 2. Limpiar memoria LangGraph
    if _aio_conn:
        # AsyncSqliteSaver: borrar filas de las tablas de checkpoints
        tablas = ["checkpoint_blobs", "checkpoint_writes", "checkpoints", "writes"]
        borradas = 0
        for tabla in tablas:
            try:
                cur = await _aio_conn.execute(f"DELETE FROM {tabla}")
                borradas += cur.rowcount
            except Exception:
                pass   # tabla puede no existir segun version de LangGraph
        await _aio_conn.commit()

        # Reconstruir el grafo con la misma conexion (DB ya limpia)
        try:
            from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
            checkpointer = AsyncSqliteSaver(_aio_conn)
            _grafo_mod.grafo_mineria = _grafo_mod.construir_grafo(checkpointer)
        except Exception as e:
            log.warning(f"No se pudo reconstruir grafo tras reset: {e}")

        log.info(f"LangGraph reset: {borradas} filas eliminadas de checkpoints SQLite")
        return {
            "estado":   "reiniciado",
            "motor":    "AsyncSqliteSaver",
            "filas_borradas": borradas,
        }
    else:
        # MemorySaver: reconstruir el grafo con saver nuevo (descarta estado en RAM)
        _grafo_mod.grafo_mineria = _grafo_mod.construir_grafo()
        log.info("LangGraph reset: grafo reconstruido con MemorySaver fresco")
        return {
            "estado": "reiniciado",
            "motor":  "MemorySaver",
        }


@app.get("/zonas")
async def listar_zonas():
    return {"zonas": list(settings.zonas)}