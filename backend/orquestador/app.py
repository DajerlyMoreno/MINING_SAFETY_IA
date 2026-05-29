"""
app.py — FastAPI del Orquestador Central (Puerto 8000).
Es el punto de entrada principal del sistema multiagente.
También provee el endpoint WebSocket para el dashboard React.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.config import settings
from backend.shared.logger import get_logger
from backend.orquestador.orquestador import Orquestador
from backend.orquestador.communication_manager import CommunicationManager
from backend.rag.rag_engine import rag

log = get_logger("orquestador_api")

# ── Estado global ─────────────────────────────────────────────────────────────
motor       = Orquestador()
comm: Optional[CommunicationManager] = None
ws_clients: list[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    global comm
    log.info("=== Iniciando Orquestador Central ===")
    rag.inicializar()
    comm = CommunicationManager()
    await comm.__aenter__()
    log.info("Orquestador listo en puerto 8000")
    yield
    await comm.__aexit__(None, None, None)
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

    # Consultar agentes en paralelo
    resp_gases, resp_imagen, resp_geo = await asyncio.gather(
        comm.analizar_gases(req.zona, req.gases),
        comm.analizar_imagen(
            req.zona,
            req.imagen.get("deteccion", "normal"),
            req.imagen.get("confianza", 0.9),
            req.imagen.get("n_personas", 0),
        ),
        comm.analizar_geo(req.zona, req.geo),
        return_exceptions=False,
    )

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
    resultados = rag.consultar(req.query, k=req.k, categoria=req.categoria)
    return {"query": req.query, "resultados": resultados}


@app.get("/zonas")
async def listar_zonas():
    return {"zonas": list(settings.zonas)}