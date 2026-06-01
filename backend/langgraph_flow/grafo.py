"""
grafo.py — Grafo LangGraph para orquestación autónoma cíclica (Capa 3).

Flujo de ejecución:
  START → ingesta → analizar_agentes → correlacionar → consultar_rag
        → razonar_llm → [condicional] → emitir_alerta | actualizar_gemelo → END

Persistencia:
  - Por defecto usa MemorySaver (funciona siempre, estado en RAM por sesión).
  - Si se llama construir_grafo(checkpointer=AsyncSqliteSaver(...)) desde el lifespan
    de app.py, el estado persiste en disco entre reinicios del servidor.
  - El lifespan de app.py se encarga de crear AsyncSqliteSaver con aiosqlite.
"""

from __future__ import annotations

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from backend.langgraph_flow.estado import EstadoMinerio
from backend.langgraph_flow.nodos import (
    nodo_ingesta,
    nodo_analizar_agentes,
    nodo_correlacionar,
    nodo_consultar_rag,
    nodo_razonar_llm,
    nodo_emitir_alerta,
    nodo_actualizar_gemelo,
)
from backend.shared.enums import NIVEL_ORDEN, NivelRiesgo
from backend.shared.logger import get_logger

log = get_logger("langgraph_grafo")


def _ruta_decision(state: EstadoMinerio) -> str:
    """
    Edge condicional después del razonamiento LLM.
    EMERGENCIA / EVACUACIÓN → alerta WhatsApp + registro crítico.
    Niveles inferiores       → actualización silenciosa del gemelo digital.
    """
    nivel = state.get("nivel_global", "SEGURO")
    try:
        orden = NIVEL_ORDEN[NivelRiesgo(nivel)]
    except (ValueError, KeyError):
        orden = 0
    return "emitir_alerta" if orden >= 4 else "actualizar_gemelo"


def construir_grafo(checkpointer=None):
    """
    Construye y compila el grafo de orquestación cíclica.

    Args:
        checkpointer: Instancia de checkpointer (AsyncSqliteSaver, MemorySaver, etc.).
                      Si es None, usa MemorySaver por defecto.
    """
    builder = StateGraph(EstadoMinerio)

    # ── Nodos ──────────────────────────────────────────────────────────────────
    builder.add_node("ingesta",           nodo_ingesta)
    builder.add_node("analizar_agentes",  nodo_analizar_agentes)
    builder.add_node("correlacionar",     nodo_correlacionar)
    builder.add_node("consultar_rag",     nodo_consultar_rag)
    builder.add_node("razonar_llm",       nodo_razonar_llm)
    builder.add_node("emitir_alerta",     nodo_emitir_alerta)
    builder.add_node("actualizar_gemelo", nodo_actualizar_gemelo)

    # ── Edges lineales ─────────────────────────────────────────────────────────
    builder.add_edge(START,              "ingesta")
    builder.add_edge("ingesta",          "analizar_agentes")
    builder.add_edge("analizar_agentes", "correlacionar")
    builder.add_edge("correlacionar",    "consultar_rag")
    builder.add_edge("consultar_rag",    "razonar_llm")

    # ── Edge condicional: alerta crítica vs gemelo digital ─────────────────────
    builder.add_conditional_edges(
        "razonar_llm",
        _ruta_decision,
        {"emitir_alerta": "emitir_alerta", "actualizar_gemelo": "actualizar_gemelo"},
    )

    builder.add_edge("emitir_alerta",     END)
    builder.add_edge("actualizar_gemelo", END)

    # ── Checkpointer ───────────────────────────────────────────────────────────
    if checkpointer is None:
        checkpointer = MemorySaver()
        log.info("Grafo LangGraph compilado — checkpointer: MemorySaver (RAM)")
    else:
        log.info(f"Grafo LangGraph compilado — checkpointer: {type(checkpointer).__name__}")

    return builder.compile(checkpointer=checkpointer)


# ── Instancia global ────────────────────────────────────────────────────────────
# Arranca con MemorySaver. El lifespan de app.py lo reemplaza con
# AsyncSqliteSaver si aiosqlite y langgraph-checkpoint-sqlite están instalados.
grafo_mineria = construir_grafo()
