"""
umbrales.py — Umbrales normativos de gases.
Fuente de verdad única para clasificación de niveles de riesgo.

Rangos normativos aplicados (Decreto 1886/2015 — Arts. 39, 40, 44):
  CH4   : 0–20 % LEL (0–1 % vol.)   · alarma 20% LEL · crítico 100% LEL (5% vol.)
  CO    : 0–20 ppm                   · alarma 25 ppm (TWA)
  CO2   : 0.03–0.5 %                 · alarma 0.5 % · crítico 3 %
  O2    : 19.5–23.5 %                · alarma <19.5 % o >23.5 % · crítico <16 %
  H2S   : 0–1 ppm                    · alarma 1 ppm (TWA) · crítico 5 ppm (STEL)
  Temp. : 14–28 °C                   · alarma 28 °C · crítico 33 °C  [Art. 44]
  Hum.  : 40–90 % RH                 · referencial
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
        (0.0, 0.99), (1.0, 1.49), (1.5, 4.99), (5.0, float("inf")),
        "Gas inflamable/explosivo. Alarma 20% LEL (1% vol.), crítico 100% LEL (5% vol.).",
        "Art. 39 + 40 Decreto 1886/2015",
        0.15, 0.06,
    ),
    "CO": UmbralGas(
        "Monóxido de Carbono", "ppm",
        (0, 24.9), (25, 49.9), (50, 199.9), (200, float("inf")),
        "Gas tóxico inodoro. Alarma 25 ppm (TWA). IDLH NIOSH: 1200 ppm.",
        "Art. 39 Decreto 1886/2015",
        5.0, 2.0,
    ),
    "CO2": UmbralGas(
        "Dióxido de Carbono", "% v/v",
        (0, 0.49), (0.5, 2.99), (3.0, 4.99), (5.0, float("inf")),
        "Asfixiante. Alarma 0.5% (5000 ppm TWA). Crítico 3%. >5% pérdida de consciencia.",
        "Art. 39 Decreto 1886/2015",
        0.08, 0.03,
    ),
    "O2": UmbralGas(
        "Oxígeno", "% v/v",
        (19.5, 23.5), (17.5, 19.49), (16.0, 17.49), (0.0, 15.99),
        "Deficiencia: <19.5% riesgo fisiológico. <16% pérdida de consciencia.",
        "Art. 118 Decreto 1886/2015 — OSHA 1910.146: <19.5% espacio confinado",
        20.9, 0.2,
    ),
    "H2S": UmbralGas(
        "Sulfuro de Hidrógeno", "ppm",
        (0, 0.9), (1.0, 4.9), (5.0, 49.9), (50, float("inf")),
        "Extremadamente tóxico. Alarma 1 ppm (TWA). Crítico 5 ppm (STEL). IDLH: 50 ppm.",
        "Art. 39 Decreto 1886/2015",
        0.15, 0.07,
    ),
    "temperatura": UmbralGas(
        "Temperatura Ambiente", "°C",
        (14, 27.9), (28, 32.9), (33, 39.9), (40, float("inf")),
        "Estrés térmico severo. Alarma 28 °C. Crítico 33 °C.",
        "Art. 44 Decreto 1886/2015",
        22.0, 3.5,
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