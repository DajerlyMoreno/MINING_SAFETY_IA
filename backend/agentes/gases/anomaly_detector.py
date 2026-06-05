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

# Umbrales de alarma para score compuesto (Art. 39 Decreto 1886/2015)
ALARMA_GAS = {"CH4": 1.0, "CO": 25.0, "CO2": 0.5, "H2S": 1.0}


def _ingenieria_caracteristicas(
    lectura: dict,
    historial: Optional[list] = None,
) -> np.ndarray:
    """
    Transforma la lectura cruda en el vector de 5 características derivadas
    que consume el IsolationForest.

    Características:
      ch4_co_ratio            CH₄ / (CO + ε)               indicador de combustión
      o2_deficit              max(0, 20.5 - O₂)             déficit de oxígeno
      gas_composite_score     Σ(valor_i / alarma_i)         peligrosidad multigas
      delta_ch4_15min         CH₄(t) − CH₄(t−1)            variación temporal
      temperatura_humedad_idx Temp × (Humedad / 100)        estrés ambiental
    """
    ch4  = lectura.get("CH4",         0.0)
    co   = lectura.get("CO",          0.0)
    co2  = lectura.get("CO2",         0.0)
    o2   = lectura.get("O2",          20.9)
    h2s  = lectura.get("H2S",         0.0)
    temp = lectura.get("temperatura", 22.0)
    hum  = lectura.get("humedad",     65.0)

    ch4_co_ratio            = ch4 / (co + 1e-9)
    o2_deficit              = max(0.0, 20.5 - o2)
    gas_composite_score     = (
        ch4 / ALARMA_GAS["CH4"] +
        co  / ALARMA_GAS["CO"]  +
        co2 / ALARMA_GAS["CO2"] +
        h2s / ALARMA_GAS["H2S"]
    )
    ch4_prev                = historial[-1].get("CH4", ch4) if historial else ch4
    delta_ch4_15min         = ch4 - ch4_prev
    temperatura_humedad_idx = temp * (hum / 100.0)

    return np.array([[
        ch4_co_ratio, o2_deficit, gas_composite_score,
        delta_ch4_15min, temperatura_humedad_idx,
    ]], dtype=np.float32)


# Valor mínimo absoluto para que un cambio brusco sea real (evita falsos positivos)
UMBRAL_ABSOLUTO_MINIMO = {
    "CH4": 0.10,   # % vol  — 10 % del umbral de alarma
    "CO":  2.5,    # ppm    — 10 % del umbral de alarma
    "H2S": 0.10,   # ppm    — 10 % del umbral de alarma
}


def _calcular_slopes(historial: list, gases: list) -> dict:
    """Regresión lineal sobre las últimas 6 lecturas de cada gas.
    Retorna la pendiente (positiva = subiendo, negativa = bajando)."""
    if not historial or len(historial) < 3:
        return {g: 0.0 for g in gases}
    n      = min(6, len(historial))
    recent = historial[-n:]
    x      = np.arange(n, dtype=np.float32)
    slopes = {}
    for gas in gases:
        y = np.array([h.get(gas, 0.0) for h in recent], dtype=np.float32)
        slopes[gas] = round(float(np.polyfit(x, y, 1)[0]), 6) if np.std(y) > 1e-9 else 0.0
    return slopes


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
            "tendencias":      {},
        }

        # 1) Isolation Forest con características derivadas
        if self._cargado and zona in self._modelos:
            try:
                X_if   = _ingenieria_caracteristicas(lectura, historial)
                scaler = self._scalers.get(zona)
                if scaler is not None:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        Xs = scaler.transform(X_if)
                else:
                    Xs = X_if

                pred  = self._modelos[zona].predict(Xs)[0]
                score = float(-self._modelos[zona].score_samples(Xs)[0])
                resultado["score_anomalia"] = round(score, 4)

                # Solo señal clara (score bien por encima del límite ~0.5).
                # Scores 0.50-0.61 son borderizos y generan falsos positivos
                # en condiciones normales de mina con gases moderadamente elevados.
                _IF_SCORE_UMBRAL = 0.62
                if pred == -1 and score >= _IF_SCORE_UMBRAL:
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

        # 3) Reglas por características derivadas
        o2_deficit = max(0.0, 20.5 - lectura.get("O2", 20.9))
        if o2_deficit > 1.0:
            resultado["es_anomalia"] = True
            if resultado["tipo_anomalia"] is None:
                resultado["tipo_anomalia"] = "patron_multivariado"
            resultado["razones"].append(
                f"Déficit O2: {o2_deficit:.2f}% (O2={lectura.get('O2', 20.9):.2f}%)"
            )
            if "O2" not in resultado["gases_afectados"]:
                resultado["gases_afectados"].append("O2")

        gas_composite = (
            lectura.get("CH4", 0.0) / ALARMA_GAS["CH4"] +
            lectura.get("CO",  0.0) / ALARMA_GAS["CO"]  +
            lectura.get("CO2", 0.0) / ALARMA_GAS["CO2"] +
            lectura.get("H2S", 0.0) / ALARMA_GAS["H2S"]
        )
        if gas_composite > 1.0 and not resultado["es_anomalia"]:
            resultado["es_anomalia"] = True
            if resultado["tipo_anomalia"] is None:
                resultado["tipo_anomalia"] = "patron_multivariado"
            resultado["razones"].append(
                f"Score compuesto de peligrosidad: {gas_composite:.2f} (umbral=1.0)"
            )

        # 4) Incremento brusco con umbral absoluto mínimo (evita falsos positivos)
        if historial and len(historial) >= 3:
            for gas, umbral_pct in UMBRAL_CAMBIO_BRUSCO.items():
                valores_recientes = [h.get(gas, 0) for h in historial[-6:]]
                media  = np.mean(valores_recientes)
                actual = lectura.get(gas, 0)
                min_abs = UMBRAL_ABSOLUTO_MINIMO.get(gas, 0)
                if media > 0 and actual >= min_abs:
                    cambio = ((actual - media) / media) * 100
                    if cambio > umbral_pct:
                        resultado["es_anomalia"] = True
                        if resultado["tipo_anomalia"] is None:
                            resultado["tipo_anomalia"] = "incremento_brusco"
                        resultado["razones"].append(
                            f"{gas}: incremento del {cambio:.0f}% "
                            f"(media={media:.3f} → actual={actual:.3f})"
                        )
                        if gas not in resultado["gases_afectados"]:
                            resultado["gases_afectados"].append(gas)

        # 5) Patrón de incendio: CO y CO2 subiendo simultáneamente
        if historial and len(historial) >= 3:
            co_prev  = np.mean([h.get("CO",  0.0) for h in historial[-3:]])
            co2_prev = np.mean([h.get("CO2", 0.0) for h in historial[-3:]])
            co_act   = lectura.get("CO",  0.0)
            co2_act  = lectura.get("CO2", 0.0)
            co_sube  = co_act  > co_prev  * 1.15 and co_act  > 5.0
            co2_sube = co2_act > co2_prev * 1.10 and co2_act > 0.05
            if co_sube and co2_sube:
                resultado["es_anomalia"] = True
                resultado["tipo_anomalia"] = "patron_incendio"
                resultado["razones"].append(
                    f"Patrón incendio: CO ({co_act:.1f} ppm) y "
                    f"CO2 ({co2_act:.3f} %) en ascenso simultáneo"
                )

        # 6) Zona de explosividad CH4 (1–5 % vol. = LEL–UEL con O2 presente)
        ch4_act = lectura.get("CH4", 0.0)
        o2_act  = lectura.get("O2",  20.9)
        if 1.0 <= ch4_act <= 5.0 and o2_act > 12.0:
            resultado["es_anomalia"] = True
            if resultado["tipo_anomalia"] not in ("patron_incendio",):
                resultado["tipo_anomalia"] = "zona_explosividad"
            resultado["razones"].append(
                f"CH4 en zona explosiva: {ch4_act:.2f} % vol. (LEL–UEL) con O2={o2_act:.1f} %"
            )
            if "CH4" not in resultado["gases_afectados"]:
                resultado["gases_afectados"].append("CH4")

        if resultado["es_anomalia"] and resultado["tipo_anomalia"] is None:
            resultado["tipo_anomalia"] = "patron_multivariado"

        # Pendientes para todas las variables con historial disponible
        if historial and len(historial) >= 3:
            resultado["tendencias"] = _calcular_slopes(historial, FEATURES)

        return resultado
