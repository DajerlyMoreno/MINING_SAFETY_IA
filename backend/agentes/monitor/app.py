"""
app.py — Agente Monitor (Puerto 8004).
Supervisa el estado global del sistema, las rondas de inspección de
sostenimiento, el cumplimiento del plan de ventilación y actualiza el
gemelo digital de la mina con el historial de incidentes por frente.
Capa 3 — LangGraph node: nodo_analizar_agentes.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.logger import get_logger
from backend.agentes.monitor.monitor import gemelo

log = get_logger("agente_monitor_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=== Agente Monitor iniciando en :8004 ===")
    log.info("Gemelo digital de la mina inicializado")
    yield
    log.info("=== Agente Monitor detenido ===")


app = FastAPI(
    title="📊 Agente Monitor — UPTC 2026",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class EventoRegistro(BaseModel):
    zona:      str = Field(example="Frente_A_Sogamoso")
    nivel:     str = Field(example="RIESGO ALTO")
    evento_id: str = Field(example="A3F1B2")


class RondaRequest(BaseModel):
    zona:      str = Field(example="Frente_A_Sogamoso")
    tipo:      str = Field(example="sostenimiento")
    inspector: str = Field(example="Juan García")


class CompletarRondaRequest(BaseModel):
    ronda_id:      str = Field(example="RONDA-0001")
    observaciones: str = Field(default="", example="Sostenimiento en buen estado")


class VentilacionCheck(BaseModel):
    zona:      str   = Field(example="Frente_A_Sogamoso")
    caudal_m3s: float = Field(example=7.5)


class EstadoRequest(BaseModel):
    zona: str = Field(default="Frente_A_Sogamoso")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"agente": "AGENTE_MONITOR", "estado": "ACTIVO", "puerto": 8004}


@app.post("/estado")
async def estado(req: EstadoRequest):
    """Consulta el estado actual del gemelo digital para una zona."""
    est = gemelo.estado_zona(req.zona)
    if est is None:
        return {
            "zona":           req.zona,
            "nivel_riesgo":   "SEGURO",
            "nivel_actual":   "SEGURO",
            "total_alertas":  0,
            "agentes":        gemelo.estados_agentes(),
        }
    return {
        "zona":          req.zona,
        "nivel_riesgo":  est["nivel_actual"],
        **est,
        "agentes":       gemelo.estados_agentes(),
    }


@app.get("/gemelo")
async def gemelo_global():
    """Retorna el resumen completo del gemelo digital de la mina."""
    return gemelo.resumen_global()


@app.post("/registrar_evento")
async def registrar_evento(req: EventoRegistro):
    """El orquestador/LangGraph registra eventos en el gemelo digital."""
    gemelo.registrar_evento(req.zona, req.nivel, req.evento_id)
    return {"status": "ok", "zona": req.zona, "nivel": req.nivel}


@app.get("/historial/{zona}")
async def historial(zona: str, n: int = 20):
    """Historial de eventos de una zona (para el dashboard)."""
    return {
        "zona":    zona,
        "eventos": gemelo.historial_zona(zona, n),
    }


@app.post("/ronda/iniciar")
async def iniciar_ronda(req: RondaRequest):
    ronda = gemelo.registrar_ronda(req.zona, req.tipo, req.inspector)
    return ronda


@app.post("/ronda/completar")
async def completar_ronda(req: CompletarRondaRequest):
    ronda = gemelo.completar_ronda(req.ronda_id, req.observaciones)
    if ronda is None:
        raise HTTPException(404, f"Ronda {req.ronda_id} no encontrada")
    return ronda


@app.post("/ventilacion/verificar")
async def verificar_ventilacion(req: VentilacionCheck):
    return gemelo.verificar_ventilacion(req.zona, req.caudal_m3s)
