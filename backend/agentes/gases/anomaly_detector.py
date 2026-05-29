"""
anomaly_detector.py - Detector de anomalias para el Agente de Gases.
Encapsula la carga del IsolationForest exportado desde Colab.
Opera en modo fallback (deteccion por reglas) si el modelo no esta disponible.
"""

from __future__ import annotations

import pickle
import warnings
from typing import Optional

import numpy as np

from backend.shared.config import settings
from backend.shared.logger import get_logger

log = get_logger("anomaly_detector")

FEATURES = ["CH4", "CO", "CO2", "O2", "H2S"]

# Umbrales de cambio brusco por gas (%)
UMBRAL_CAMBIO_BRUSCO = {
    "CH4": 50.0,
    "CO":  80.0,
    "H2S": 100.0,
}


class AnomalyDetector:
    """
    Carga los modelos IsolationForest pre-entrenados en Colab
    y detecta anomalias en lecturas de sensores de gases.
    Si el modelo no esta disponible, opera en modo fallback
    (solo deteccion por reglas) sin bloquear el arranque.
    """

    def __init__(self) -> None:
        self._modelos: dict = {}
        self._scalers: dict = {}
        self._cargado = False

    def cargar(self) -> None:
        """
        Carga modelos desde el archivo .pkl exportado de Colab.
        Si el archivo no existe o tiene formato inesperado,
        activa modo degradado (solo reglas).
        """
        ruta = settings.model_paths.isolation_forest_gases
        if not ruta.exists():
            log.warning(
                f"IsolationForest no encontrado en {ruta}. "
                "Operando en modo fallback (deteccion solo por reglas)."
            )
            return

        log.info(f"Cargando IsolationForest desde {ruta}")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with open(ruta, "rb") as f:
                    data = pickle.load(f)

            if isinstance(data, dict) and "modelos" in data:
                self._modelos = data["modelos"]
                self._scalers = data.get("scalers", {})
            elif isinstance(data, dict):
                self._modelos = data
                self._scalers = {}
            else:
                log.warning("Formato de pickle inesperado. Modo fallback activado.")
                return

            self._cargado = True
            zonas = list(self._modelos.keys())
            log.info(f"IsolationForest cargado para zonas: {zonas}")

        except Exception as e:
            log.warning(
                f"Error al cargar IsolationForest: {e}. "
                "Operando en modo fallback (deteccion solo por reglas)."
            )

    def detectar(
        self,
        lectura: dict,
        zona: str,
        historial: Optional[list] = None,
    ) -> dict:
        """
        Detecta si una lectura es anomala usando IsolationForest + reglas.

        Args:
            lectura:   Dict con keys CH4, CO, CO2, O2, H2S.
            zona:      Zona minera.
            historial: Ultimas N lecturas para detectar cambios bruscos.

        Returns:
            Dict con es_anomalia, score_anomalia, tipo_anomalia, razones, gases_afectados.
        """
        resultado = {
            "es_anomalia":     False,
            "score_anomalia":  0.0,
            "tipo_anomalia":   None,
            "razones":         [],
            "gases_afectados": [],
        }

        # 1) Isolation Forest (solo si modelo disponible para esta zona)
        if self._cargado and zona in self._modelos:
            try:
                X = np.array([[lectura.get(g, 0) for g in FEATURES]])
                scaler = self._scalers.get(zona)
                if scaler is not None:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        Xs = scaler.transform(X)
                else:
                    Xs = X

                pred  = self._modelos[zona].predict(Xs)[0]
                score = float(-self._modelos[zona].score_samples(Xs)[0])
                resultado["score_anomalia"] = round(score, 4)

                if pred == -1:
                    resultado["es_anomalia"] = True
                    resultado["razones"].append(
                        f"Isolation Forest: score {score:.3f} supera umbral del modelo"
                    )
            except Exception as e:
                log.debug(f"IsolationForest error para {zona}: {e}")

        # 2) Sensor defectuoso (valor 0 sospechoso)
        for gas in FEATURES:
            val = lectura.get(gas, 0)
            if val == 0.0 and gas not in ("H2S",):
                resultado["es_anomalia"] = True
                resultado["tipo_anomalia"] = "falla_sensor"
                resultado["razones"].append(f"Sensor {gas}: lectura cero sospechosa")
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
                            f"(media={media:.3f} -> actual={lectura.get(gas,0):.3f})"
                        )
                        if gas not in resultado["gases_afectados"]:
                            resultado["gases_afectados"].append(gas)

        if resultado["es_anomalia"] and resultado["tipo_anomalia"] is None:
            resultado["tipo_anomalia"] = "patron_multivariado"

        return resultado
