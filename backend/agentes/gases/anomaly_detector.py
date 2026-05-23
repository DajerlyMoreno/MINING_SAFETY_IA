"""
anomaly_detector.py — Detector de anomalías para el Agente de Gases.
Encapsula la carga del IsolationForest exportado desde Colab y
provee métodos de detección con explicaciones detalladas.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from backend.shared.config import settings
from backend.shared.exceptions import ModeloNoEncontrado, ZonaNoSoportada
from backend.shared.logger import get_logger

log = get_logger("anomaly_detector")

FEATURES = ["CH4", "CO", "CO2", "O2", "H2S"]

# Umbrales de cambio brusco por gas (%)
UMBRAL_CAMBIO_BRUSCO = {
    "CH4": 50.0,
    "CO": 80.0,
    "H2S": 100.0,
}


class AnomalyDetector:
    """
    Carga los modelos IsolationForest pre-entrenados en Colab
    y detecta anomalías en lecturas de sensores de gases.
    """

    def __init__(self) -> None:
        self._modelos:  dict[str, IsolationForest] = {}
        self._scalers:  dict[str, StandardScaler]  = {}
        self._cargado = False

    def cargar(self) -> None:
        """Carga modelos desde el archivo .pkl exportado de Colab."""
        ruta = settings.model_paths.isolation_forest_gases
        if not ruta.exists():
            raise ModeloNoEncontrado(str(ruta))

        log.info(f"Cargando IsolationForest desde {ruta}")
        with open(ruta, "rb") as f:
            data = pickle.load(f)

        self._modelos = data["modelos"]
        self._scalers = data["scalers"]
        self._cargado = True

        zonas = list(self._modelos.keys())
        log.info(f"IsolationForest cargado para zonas: {zonas}")

    def detectar(
        self,
        lectura: dict[str, float],
        zona: str,
        historial: Optional[list[dict]] = None,
    ) -> dict:
        """
        Detecta si una lectura es anómala.

        Args:
            lectura:  Dict con keys CH4, CO, CO2, O2, H2S.
            zona:     Zona minera de la lectura.
            historial: Últimas N lecturas para detectar cambios bruscos.

        Returns:
            Dict con es_anomalia, score, tipo, razones, gases_afectados.
        """
        if not self._cargado:
            raise RuntimeError("Llamar a cargar() antes de detectar()")
        if zona not in self._modelos:
            raise ZonaNoSoportada(zona)

        resultado = {
            "es_anomalia":    False,
            "score_anomalia": 0.0,
            "tipo_anomalia":  None,
            "razones":        [],
            "gases_afectados": [],
        }

        # 1) Isolation Forest
        X = np.array([[lectura.get(g, 0) for g in FEATURES]])
        Xs = self._scalers[zona].transform(X)
        pred = self._modelos[zona].predict(Xs)[0]
        score = float(-self._modelos[zona].score_samples(Xs)[0])
        resultado["score_anomalia"] = round(score, 4)

        if pred == -1:
            resultado["es_anomalia"] = True
            resultado["razones"].append(
                f"Isolation Forest: score {score:.3f} supera umbral del modelo"
            )

        # 2) Sensor defectuoso (valor 0 o extremo)
        for gas in FEATURES:
            val = lectura.get(gas, 0)
            if val == 0.0 and gas not in ("H2S",):
                resultado["es_anomalia"] = True
                resultado["tipo_anomalia"] = "falla_sensor"
                resultado["razones"].append(
                    f"Sensor {gas}: lectura cero sospechosa"
                )
                resultado["gases_afectados"].append(gas)

        # 3) Incremento brusco (si hay historial)
        if historial and len(historial) >= 3:
            for gas, umbral_pct in UMBRAL_CAMBIO_BRUSCO.items():
                valores_recientes = [h.get(gas, 0) for h in historial[-6:]]
                media = np.mean(valores_recientes)
                if media > 0:
                    cambio = ((lectura.get(gas, 0) - media) / media) * 100
                    if cambio > umbral_pct:
                        resultado["es_anomalia"] = True
                        if resultado["tipo_anomalia"] is None:
                            resultado["tipo_anomalia"] = "incremento_brusco"
                        resultado["razones"].append(
                            f"{gas}: incremento del {cambio:.0f}% "
                            f"(media={media:.3f} → actual={lectura.get(gas,0):.3f})"
                        )
                        if gas not in resultado["gases_afectados"]:
                            resultado["gases_afectados"].append(gas)

        if resultado["es_anomalia"] and resultado["tipo_anomalia"] is None:
            resultado["tipo_anomalia"] = "patron_multivariado"

        return resultado