"""
app.py — Agente de Imágenes (Puerto 8002).
Procesa la clasificación visual de cámaras IP instaladas en intersecciones
y frentes de avance. Arquitectura preparada para modelos entrenados con cGANs.
Capa 3 — LangGraph node: nodo_analizar_agentes.
"""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag
from backend.agentes.imagenes.analizador import analizar, CLASES_RIESGO

log = get_logger("agente_imagenes_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=== Agente de Imágenes iniciando en :8002 ===")
    rag.inicializar()
    log.info("Agente de Imágenes listo — esperando clasificaciones de cámara IP")
    yield
    log.info("=== Agente de Imágenes detenido ===")


app = FastAPI(
    title="📷 Agente de Imágenes — UPTC 2026",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


class LecturaImagen(BaseModel):
    zona:      str   = Field(example="Frente_A_Sogamoso")
    deteccion: str   = Field(example="normal")
    confianza: float = Field(default=0.9, ge=0.0, le=1.0, example=0.95)
    n_personas: int  = Field(default=0, ge=0, example=3)


@app.get("/health")
async def health():
    return {
        "agente":  "AGENTE_IMAGENES",
        "estado":  "ACTIVO",
        "puerto":  8002,
        "clases":  list(CLASES_RIESGO.keys()),
        "nota":    "Arquitectura preparada para modelos cGAN-entrenados (Capa 1)",
    }


@app.post("/analizar")
async def analizar_imagen(req: LecturaImagen):
    return analizar(req.zona, req.deteccion, req.confianza, req.n_personas)


@app.post(
    "/ciclo/{zona}",
    summary="Ciclo autónomo — recolecta de la cámara y entrega análisis",
)
async def ciclo_autonomo(zona: str):
    """
    El agente lee la clasificación de la cámara IP del simulador y retorna el análisis.
    """
    import httpx
    from backend.shared.config import settings
    from fastapi import HTTPException

    sim_url = f"http://{settings.simulador.host}:{settings.simulador.port}/sensores/imagen/{zona}"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(sim_url)
            resp.raise_for_status()
            datos = resp.json()
    except Exception as e:
        raise HTTPException(503, f"Simulador no disponible: {e}")

    return analizar(
        zona=zona,
        deteccion=datos.get("deteccion", "normal"),
        confianza=datos.get("confianza", 0.9),
        n_personas=datos.get("n_personas", 0),
    )


@app.get("/clases")
async def listar_clases():
    """Lista las clases de detección soportadas (salidas del modelo de visión)."""
    return {
        "clases": {k: v.value for k, v in CLASES_RIESGO.items()},
        "total":  len(CLASES_RIESGO),
    }
