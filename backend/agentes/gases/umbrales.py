"""
umbrales.py — Umbrales normativos de gases (Decreto 1886/2015 + OSHA/NIOSH).
Fuente de verdad única para clasificación de niveles de riesgo.
"""

from dataclasses import dataclass
from typing import Tuple
from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN


@dataclass(frozen=True)
class UmbralGas:
    nombre:             str
    unidad:             str
    seguro:             Tuple[float, float]
    precaucion:         Tuple[float, float]
    riesgo_alto:        Tuple[float, float]
    evacuacion:         Tuple[float, float]
    descripcion_riesgo: str
    articulo_decreto:   str
    normal_media:       float
    normal_std:         float


UMBRALES_GAS: dict[str, UmbralGas] = {
    "CH4": UmbralGas(
        "Metano", "% v/v",
        (0.0, 0.9), (1.0, 1.49), (1.5, 4.99), (5.0, float("inf")),
        "Gas inflamable/explosivo (LEL 5%, UEL 15%). Principal causa de explosiones.",
        "Art. 118-121 Decreto 1886/2015 — MSHA LEL >1%",
        0.4, 0.15,
    ),
    "CO": UmbralGas(
        "Monóxido de Carbono", "ppm",
        (0, 24.9), (25, 49.9), (50, 199.9), (200, float("inf")),
        "Gas tóxico inodoro. TLV-TWA ACGIH: 25 ppm. IDLH NIOSH: 1200 ppm.",
        "Art. 123 Decreto 1886/2015 — OSHA PEL 50 ppm",
        12.0, 4.0,
    ),
    "CO2": UmbralGas(
        "Dióxido de Carbono", "% v/v",
        (0, 0.49), (0.5, 1.49), (1.5, 2.99), (3.0, float("inf")),
        "Asfixiante. >3% dificultad respiratoria severa. >5% pérdida de consciencia.",
        "Art. 119 Decreto 1886/2015 — OSHA PEL 5000 ppm",
        0.15, 0.06,
    ),
    "O2": UmbralGas(
        "Oxígeno", "% v/v",
        (20.5, 23.5), (19.5, 20.49), (18.0, 19.49), (0.0, 17.99),
        "Deficiencia: <19.5% riesgo fisiológico. <16% pérdida de consciencia.",
        "Art. 118 Decreto 1886/2015 — OSHA 1910.146: <19.5% espacio confinado",
        20.9, 0.2,
    ),
    "H2S": UmbralGas(
        "Sulfuro de Hidrógeno", "ppm",
        (0, 0.9), (1.0, 9.9), (10, 49.9), (50, float("inf")),
        "Extremadamente tóxico. NIOSH IDLH: 50 ppm. Parálisis olfativa a 100 ppm.",
        "OSHA PEL 20 ppm (techo) — MSHA 10 ppm TWA",
        0.3, 0.12,
    ),
}


def clasificar_gas(gas: str, valor: float) -> NivelRiesgo:
    """Clasifica el nivel de riesgo de una lectura de gas según normativa."""
    u = UMBRALES_GAS[gas]
    if gas == "O2":   # lógica invertida
        if valor < u.evacuacion[1]:     return NivelRiesgo.EVACUACION
        elif valor < u.riesgo_alto[1]:  return NivelRiesgo.RIESGO_ALTO
        elif valor < u.precaucion[1]:   return NivelRiesgo.PRECAUCION
        else:                           return NivelRiesgo.SEGURO
    else:
        if valor >= u.evacuacion[0]:    return NivelRiesgo.EVACUACION
        elif valor >= u.riesgo_alto[0]: return NivelRiesgo.RIESGO_ALTO
        elif valor >= u.precaucion[0]:  return NivelRiesgo.PRECAUCION
        else:                           return NivelRiesgo.SEGURO