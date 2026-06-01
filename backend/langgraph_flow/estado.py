"""
estado.py — Estado persistente del grafo LangGraph (Capa 3).
TypedDict con memoria acumulativa via Annotated[list, operator.add].
El MemorySaver en grafo.py persiste este estado entre ciclos de monitoreo
usando thread_id=zona, implementando el flujo cíclico requerido.
"""

from __future__ import annotations

import operator
from typing import Annotated, Optional
from typing_extensions import TypedDict


class EstadoMinerio(TypedDict):
    """Estado completo de un ciclo de orquestación por zona minera."""

    # ── Entradas del ciclo actual ──────────────────────────────────────────────
    zona: str
    gases: dict
    imagen: dict
    geo: dict

    # ── Respuestas de agentes especializados ───────────────────────────────────
    resp_gases: Optional[dict]
    resp_imagen: Optional[dict]
    resp_geo: Optional[dict]
    resp_monitor: Optional[dict]

    # ── Resultado de correlación multiagente ───────────────────────────────────
    nivel_global: str
    correlaciones: list[str]
    acciones_globales: list[str]

    # ── RAG (normativa recuperada) ─────────────────────────────────────────────
    docs_rag: list[dict]
    normativa_titulos: list[str]

    # ── LLM (razonamiento contextual) ─────────────────────────────────────────
    diagnostico_llm: str
    acciones_llm: list[str]
    referencia_llm: str
    pronostico_llm: str

    # ── Decisión final ─────────────────────────────────────────────────────────
    evento_id: str
    requiere_alerta_critica: bool

    # ── Memoria persistente entre ciclos (se acumula con operator.add) ─────────
    # Cada llamada al grafo con el mismo thread_id añade a estas listas.
    # El MemorySaver garantiza que el estado se preserve entre invocaciones.
    historial_niveles: Annotated[list[str], operator.add]
    historial_eventos: Annotated[list[dict], operator.add]

    # Contador de ciclos completados para esta zona
    iteracion: int
