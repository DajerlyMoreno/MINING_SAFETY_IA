"""
umbrales_geo.py — Umbrales geomecánicos basados en Decreto 1886/2015
y criterios ISRM (International Society for Rock Mechanics).
"""

from backend.shared.enums import NivelRiesgo

# (límite_superior, nivel_riesgo) — se evalúa en orden, primer match gana.
# Para indice_estabilidad la lógica es invertida (valores bajos = peligro).
UMBRALES: dict[str, list[tuple]] = {
    "deformacion_mm": [
        (5.0,  NivelRiesgo.SEGURO),
        (10.0, NivelRiesgo.PRECAUCION),
        (20.0, NivelRiesgo.RIESGO_ALTO),
        (35.0, NivelRiesgo.EMERGENCIA),
        (float("inf"), NivelRiesgo.EVACUACION),
    ],
    "convergencia_mm": [
        (3.0,  NivelRiesgo.SEGURO),
        (6.0,  NivelRiesgo.PRECAUCION),
        (12.0, NivelRiesgo.RIESGO_ALTO),
        (20.0, NivelRiesgo.EMERGENCIA),
        (float("inf"), NivelRiesgo.EVACUACION),
    ],
    "vibracion_mms": [
        (5.0,  NivelRiesgo.SEGURO),
        (10.0, NivelRiesgo.PRECAUCION),
        (15.0, NivelRiesgo.RIESGO_ALTO),
        (25.0, NivelRiesgo.EMERGENCIA),
        (float("inf"), NivelRiesgo.EVACUACION),
    ],
    "presion_kpa": [
        (50.0,  NivelRiesgo.SEGURO),
        (80.0,  NivelRiesgo.PRECAUCION),
        (120.0, NivelRiesgo.RIESGO_ALTO),
        (180.0, NivelRiesgo.EMERGENCIA),
        (float("inf"), NivelRiesgo.EVACUACION),
    ],
}

# Variables con semántica invertida (menor valor = mayor riesgo)
UMBRALES_INVERTIDOS: dict[str, list[tuple]] = {
    "indice_estabilidad": [
        # si valor <= límite → ese nivel
        (0.25, NivelRiesgo.EVACUACION),
        (0.40, NivelRiesgo.EMERGENCIA),
        (0.55, NivelRiesgo.RIESGO_ALTO),
        (0.70, NivelRiesgo.PRECAUCION),
        (float("inf"), NivelRiesgo.SEGURO),
    ],
}

ACCIONES: dict[NivelRiesgo, list[str]] = {
    NivelRiesgo.SEGURO: [
        "Monitoreo de rutina — parámetros geomecánicos normales",
    ],
    NivelRiesgo.PRECAUCION: [
        "Incrementar frecuencia de inspección visual del sostenimiento",
        "Registrar tendencia de convergencia en el libro de mina (Art. 89)",
    ],
    NivelRiesgo.RIESGO_ALTO: [
        "Suspender avance en el frente afectado",
        "Reforzar sostenimiento: pernos adicionales cada 0.5 m en corona",
        "Notificar al ingeniero geomecánico de turno",
    ],
    NivelRiesgo.EMERGENCIA: [
        "🚨 EVACUACIÓN PARCIAL — retirar personal del nivel afectado",
        "Activar plan de soporte de emergencia (cerchas HEB 160 o similar)",
        "Cortar acceso y señalizar zona de exclusión",
    ],
    NivelRiesgo.EVACUACION: [
        "🚨🚨 EVACUACIÓN TOTAL — riesgo de colapso inminente",
        "Activar Defensa Civil y notificar ANM (Art. 68 D.1886)",
        "No reingresar hasta inspección geotécnica oficial completa",
    ],
}


def clasificar(variable: str, valor: float) -> NivelRiesgo:
    if variable in UMBRALES_INVERTIDOS:
        for limite, nivel in UMBRALES_INVERTIDOS[variable]:
            if valor <= limite:
                return nivel
        return NivelRiesgo.SEGURO
    umbrales = UMBRALES.get(variable, [])
    for limite, nivel in umbrales:
        if valor <= limite:
            return nivel
    return NivelRiesgo.EVACUACION
