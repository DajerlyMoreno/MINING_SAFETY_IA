"""
enums.py — Enumeraciones globales compartidas por todos los módulos.
"""

from enum import Enum


class NivelRiesgo(str, Enum):
    SEGURO      = "SEGURO"
    INFORMATIVO = "INFORMATIVO"
    PRECAUCION  = "PRECAUCIÓN"
    RIESGO_ALTO = "RIESGO ALTO"
    EMERGENCIA  = "EMERGENCIA"
    EVACUACION  = "EVACUACIÓN INMEDIATA"


class EstadoAgente(str, Enum):
    ACTIVO    = "ACTIVO"
    DEGRADADO = "DEGRADADO"
    OFFLINE   = "OFFLINE"
    ERROR     = "ERROR"


class TipoAgente(str, Enum):
    GASES       = "AGENTE_GASES"
    IMAGENES    = "AGENTE_IMAGENES"
    GEOMECANICO = "AGENTE_GEOMECANICO"
    MONITOR     = "AGENTE_MONITOR"
    ORQUESTADOR = "ORQUESTADOR"


class TipoEvento(str, Enum):
    LECTURA_NORMAL     = "LECTURA_NORMAL"
    ANOMALIA_DETECTADA = "ANOMALIA_DETECTADA"
    PREDICCION_CRITICA = "PREDICCION_CRITICA"
    CORRELACION_CRITICA = "CORRELACION_CRITICA"
    EVACUACION_DECLARADA = "EVACUACION_DECLARADA"
    AGENTE_OFFLINE     = "AGENTE_OFFLINE"
    SENSOR_DEFECTUOSO  = "SENSOR_DEFECTUOSO"


# Orden numérico para comparación de niveles
NIVEL_ORDEN: dict[NivelRiesgo, int] = {
    NivelRiesgo.SEGURO:      0,
    NivelRiesgo.INFORMATIVO: 1,
    NivelRiesgo.PRECAUCION:  2,
    NivelRiesgo.RIESGO_ALTO: 3,
    NivelRiesgo.EMERGENCIA:  4,
    NivelRiesgo.EVACUACION:  5,
}


def nivel_mayor(a: NivelRiesgo, b: NivelRiesgo) -> NivelRiesgo:
    """Retorna el nivel de riesgo mayor entre dos."""
    return a if NIVEL_ORDEN[a] >= NIVEL_ORDEN[b] else b