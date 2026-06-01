"""
analizador.py — Análisis de imágenes de cámaras IP en galerías.
Arquitectura preparada para integrar modelos cGAN-entrenados (Capa 1).
En la versión actual recibe el campo 'deteccion' del simulador,
que emula la salida de un clasificador de visión entrenado con datos sintéticos.
"""

from __future__ import annotations

from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN
from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag

log = get_logger("agente_imagenes")

# Mapeo clasificación visual → nivel de riesgo
# Estas clases son las que generaría el modelo entrenado con cGANs
CLASES_RIESGO: dict[str, NivelRiesgo] = {
    "normal":            NivelRiesgo.SEGURO,
    "polvo_leve":        NivelRiesgo.INFORMATIVO,
    "humedad_pared":     NivelRiesgo.PRECAUCION,
    "deformacion_leve":  NivelRiesgo.PRECAUCION,
    "cercha_deformada":  NivelRiesgo.RIESGO_ALTO,
    "perno_roto":        NivelRiesgo.RIESGO_ALTO,
    "polvo_excesivo":    NivelRiesgo.RIESGO_ALTO,
    "derrumbe_parcial":  NivelRiesgo.RIESGO_ALTO,
    "infiltracion":      NivelRiesgo.EMERGENCIA,
    "humo":              NivelRiesgo.EMERGENCIA,
    "fuego":             NivelRiesgo.EVACUACION,
    "derrumbe_total":    NivelRiesgo.EVACUACION,
}

ACCIONES: dict[NivelRiesgo, list[str]] = {
    NivelRiesgo.SEGURO:      ["Cámara operativa — sin anomalías visuales detectadas"],
    NivelRiesgo.INFORMATIVO: ["Registrar condición visual en bitácora de turno"],
    NivelRiesgo.PRECAUCION:  [
        "Inspección visual directa por parte del capataz",
        "Revisar estado del sostenimiento en zona de cámara",
    ],
    NivelRiesgo.RIESGO_ALTO: [
        "Evacuar frente — anomalía estructural o ambiental detectada",
        "Activar protocolo de reforzamiento de sostenimiento",
        "Notificar al ingeniero residente con registro fotográfico",
    ],
    NivelRiesgo.EMERGENCIA:  [
        "🚨 EVACUACIÓN — humo, fuego o infiltración detectada por cámara",
        "Activar Plan de Emergencia contra Incendios Mineros (PECI)",
        "Cortar equipos no-ATEX y maximizar ventilación",
    ],
    NivelRiesgo.EVACUACION:  [
        "🚨🚨 EVACUACIÓN TOTAL INMEDIATA",
        "Cortar toda la energía eléctrica del nivel",
        "Activar alarma general: 3 pitidos cortos + 1 largo",
    ],
}

DESCRIPCIONES: dict[str, str] = {
    "normal":            "Galería en condiciones visuales normales",
    "polvo_leve":        "Partículas de polvo dentro de rango aceptable",
    "humedad_pared":     "Humedad visible en paredes — posible filtración menor",
    "deformacion_leve":  "Deformación incipiente del sostenimiento",
    "cercha_deformada":  "Cercha metálica con deformación visible — reforzar",
    "perno_roto":        "Perno de anclaje fracturado — riesgo de desprendimiento",
    "polvo_excesivo":    "Concentración de polvo combustible fuera de límites",
    "derrumbe_parcial":  "Caída parcial de roca — zona bloqueada",
    "infiltracion":      "Irrupción de agua freática activa",
    "humo":              "Humo detectado — posible inicio de incendio",
    "fuego":             "Llama visible — incendio activo en galería",
    "derrumbe_total":    "Colapso total de la galería — acceso bloqueado",
}


def analizar(zona: str, deteccion: str, confianza: float, n_personas: int) -> dict:
    """
    Analiza la clasificación visual de la cámara IP y genera diagnóstico.
    """
    nivel = CLASES_RIESGO.get(deteccion, NivelRiesgo.INFORMATIVO)

    docs_rag: list[dict] = []
    if NIVEL_ORDEN[nivel] >= 2:
        docs_rag = rag.consultar(
            f"visual {deteccion} galeria sostenimiento protocolo emergencia", k=2
        )

    acciones = list(ACCIONES.get(nivel, []))
    if n_personas > 0 and NIVEL_ORDEN[nivel] >= 3:
        acciones.insert(
            0,
            f"⚠️ {n_personas} persona(s) detectada(s) en zona de riesgo — evacuar inmediatamente",
        )

    descripcion = DESCRIPCIONES.get(deteccion, f"Detección: {deteccion}")

    return {
        "zona":                  zona,
        "nivel_riesgo":          nivel.value,
        "deteccion":             deteccion,
        "descripcion":           descripcion,
        "confianza":             confianza,
        "n_personas_detectadas": n_personas,
        "acciones":              acciones,
        "normativa":             [d["titulo"] for d in docs_rag],
        "explicacion": (
            f"Análisis visual — {zona}: {descripcion} "
            f"(confianza {confianza:.0%}). Personal detectado: {n_personas}."
        ),
        "datos_crudos": {
            "deteccion":  deteccion,
            "confianza":  confianza,
            "n_personas": n_personas,
        },
    }
