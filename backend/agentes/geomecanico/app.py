"""
app.py — Agente Geomecánico (Puerto 8003).
Procesa lecturas de extensómetros, convergímetros y sensores de presión
para detectar inestabilidad estructural, subsidencia y riesgo de irrupción
de agua freática. Capa 3 — LangGraph node: nodo_analizar_agentes.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag
from backend.agentes.geomecanico.analizador import analizar

log = get_logger("agente_geo_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=== Agente Geomecánico iniciando en :8003 ===")
    rag.inicializar()
    log.info("Agente Geomecánico listo")
    yield
    log.info("=== Agente Geomecánico detenido ===")


app = FastAPI(
    title="⛏ Agente Geomecánico — UPTC 2026",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class LecturaGeo(BaseModel):
    zona:               str   = Field(example="Frente_A_Sogamoso")
    deformacion_mm:     Optional[float] = Field(default=None, example=3.5)
    convergencia_mm:    Optional[float] = Field(default=None, example=1.8)
    vibracion_mms:      Optional[float] = Field(default=None, example=4.2)
    presion_kpa:        Optional[float] = Field(default=None, example=42.0)
    indice_estabilidad: Optional[float] = Field(default=None, example=0.82)


@app.get("/health")
async def health():
    return {"agente": "AGENTE_GEOMECANICO", "estado": "ACTIVO", "puerto": 8003}


@app.post("/analizar")
async def analizar_geo(req: LecturaGeo):
    lectura = req.model_dump(exclude={"zona"}, exclude_none=True)
    return analizar(req.zona, lectura)


@app.post(
    "/ciclo/{zona}",
    summary="Ciclo autónomo — recolecta del simulador y entrega análisis",
)
async def ciclo_autonomo(zona: str):
    """
    El agente lee sensores geomecánicos del simulador, los analiza y entrega resultado.
    """
    import httpx
    from backend.shared.config import settings

    sim_url = f"http://{settings.simulador.host}:{settings.simulador.port}/sensores/geo/{zona}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(sim_url)
            resp.raise_for_status()
            datos = resp.json()
    except Exception as e:
        raise HTTPException(503, f"Simulador no disponible: {e}")

    lectura = {k: v for k, v in datos.items() if k not in ("zona", "timestamp", "sensor")}
    return analizar(zona, lectura)


@app.get("/estado")
async def estado(zona: str = "Frente_A_Sogamoso"):
    """El Agente Monitor llama a este endpoint para obtener estado geomecánico."""
    return {
        "agente": "AGENTE_GEOMECANICO",
        "zona":   zona,
        "estado": "ACTIVO",
        "nivel_riesgo": "SEGURO",
    }
