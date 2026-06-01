"""
analizador.py — Análisis geomecánico.
Procesa lecturas de extensómetros, convergímetros y sensores de presión
para predecir zonas de inestabilidad, subsidencia e irrupción de agua freática.
"""

from __future__ import annotations

from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN, nivel_mayor
from backend.shared.logger import get_logger
from backend.agentes.geomecanico.umbrales_geo import clasificar, ACCIONES
from backend.rag.rag_engine import rag

log = get_logger("agente_geomecanico")

VARIABLES = [
    "deformacion_mm",
    "convergencia_mm",
    "vibracion_mms",
    "presion_kpa",
    "indice_estabilidad",
]


def analizar(zona: str, lectura: dict) -> dict:
    """
    Analiza lecturas geomecánicas y retorna diagnóstico estructural completo.
    Incluye predicción de variables críticas si hay riesgo >= RIESGO_ALTO.
    """
    resultados: dict[str, dict] = {}
    nivel_max = NivelRiesgo.SEGURO
    criticas: list[dict] = []

    for var in VARIABLES:
        if var not in lectura:
            continue
        valor = float(lectura[var])
        nivel = clasificar(var, valor)
        resultados[var] = {"valor": valor, "nivel": nivel.value}
        nivel_max = nivel_mayor(nivel_max, nivel)
        if NIVEL_ORDEN[nivel] >= 2:
            criticas.append({"variable": var, "valor": valor, "nivel": nivel.value})

    # Consulta RAG si hay riesgo geomecánico significativo
    docs_rag: list[dict] = []
    if NIVEL_ORDEN[nivel_max] >= 2:
        query = (
            f"geomecanica deformacion sostenimiento convergencia {nivel_max.value} "
            "decreto 1886 estabilidad galeria"
        )
        docs_rag = rag.consultar(query, k=2)

    acciones = list(ACCIONES.get(nivel_max, []))
    explicacion = _explicacion(zona, nivel_max, criticas)

    return {
        "zona":               zona,
        "nivel_riesgo":       nivel_max.value,
        "variables":          resultados,
        "variables_criticas": criticas,
        "acciones":           acciones,
        "normativa":          [d["titulo"] for d in docs_rag],
        "explicacion":        explicacion,
        "datos_crudos":       lectura,
        # Lista no vacía cuando hay riesgo alto → el orquestador lo usa
        # para activar la predicción de tendencia creciente
        "predicciones":       criticas if NIVEL_ORDEN[nivel_max] >= 3 else [],
    }


def _explicacion(zona: str, nivel: NivelRiesgo, criticas: list[dict]) -> str:
    if not criticas:
        return f"Zona {zona}: parámetros geomecánicos dentro de límites normales (ISRM)."
    detalle = ", ".join(f"{c['variable']}={c['valor']:.2f}" for c in criticas)
    return (
        f"Zona {zona} — nivel {nivel.value}: "
        f"variables fuera de umbral: {detalle}. "
        "Revisar integridad del sostenimiento y estabilidad del macizo rocoso."
    )
