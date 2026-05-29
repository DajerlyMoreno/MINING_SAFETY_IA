"""
predictor.py — Predictor LSTM para el Agente de Gases.

Inferencia en NumPy puro: no depende de keras ni tensorflow en absoluto.
Los modelos fueron guardados con Keras 3.13.2; sus pesos se leen directamente
del archivo model.weights.h5 que contiene cada .keras (que es un ZIP).

Arquitectura de cada modelo:
  InputLayer(24, 5)
  -> LSTM(128, return_sequences=True)
  -> Dropout (ignorado en inferencia)
  -> LSTM(64, return_sequences=False)
  -> Dropout (ignorado en inferencia)
  -> Dense(30)   [30 = 6 horizontes x 5 gases]
"""

from __future__ import annotations

import io
import pickle
import warnings
import zipfile
from pathlib import Path

import numpy as np

from backend.shared.config import settings
from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN
from backend.shared.logger import get_logger

warnings.filterwarnings("ignore", category=UserWarning)
log = get_logger("predictor_lstm")

FEATURES = ["CH4", "CO", "CO2", "O2", "H2S"]

GAS_STATS_DEFAULT = {
    "CH4": (0.28, 0.10),
    "CO":  (5.8,  2.5),
    "CO2": (0.11, 0.05),
    "O2":  (20.6, 0.15),
    "H2S": (0.18, 0.08),
}


# ── Funciones de activacion ────────────────────────────────────────────────────
def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -88, 88)))

def _tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)


# ── Celda LSTM en NumPy ────────────────────────────────────────────────────────
def _lstm_forward(X: np.ndarray, W: np.ndarray, U: np.ndarray,
                  b: np.ndarray, return_sequences: bool) -> np.ndarray:
    """
    X: (T, input_dim)
    W: (input_dim, units*4)  kernel
    U: (units, units*4)      recurrent_kernel
    b: (units*4,)            bias
    Retorna (T, units) si return_sequences else (1, units)
    """
    T, _ = X.shape
    units = W.shape[1] // 4
    h = np.zeros(units, dtype=np.float32)
    c = np.zeros(units, dtype=np.float32)
    outputs = []

    for t in range(T):
        z = X[t] @ W + h @ U + b          # (units*4,)
        i = _sigmoid(z[0         :units  ])
        f = _sigmoid(z[units     :2*units])
        g = _tanh   (z[2*units   :3*units])
        o = _sigmoid(z[3*units   :4*units])
        c = f * c + i * g
        h = o * _tanh(c)
        outputs.append(h.copy())

    outputs = np.array(outputs, dtype=np.float32)   # (T, units)
    return outputs if return_sequences else outputs[-1:]


# ── Modelo LSTM cargado desde H5 ───────────────────────────────────────────────
class _ModeloLSTMNumpy:
    """Inferencia de un modelo Sequential LSTM+Dense en NumPy."""

    def __init__(self, W1, U1, b1, W2, U2, b2, Wd, bd):
        self.W1, self.U1, self.b1 = W1, U1, b1   # LSTM 1 (128 units)
        self.W2, self.U2, self.b2 = W2, U2, b2   # LSTM 2 (64 units)
        self.Wd, self.bd = Wd, bd                 # Dense (30 units)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """X: (1, 24, 5) -> (1, 6, 5)"""
        x = X[0].astype(np.float32)               # (24, 5)
        x = _lstm_forward(x, self.W1, self.U1, self.b1, return_sequences=True)   # (24, 128)
        x = _lstm_forward(x, self.W2, self.U2, self.b2, return_sequences=False)  # (1,  64)
        x = x[0] @ self.Wd + self.bd              # (30,)
        # Reorganizar: (30,) -> (6, 5)
        return x.reshape(1, 6, 5)


def _cargar_modelo_numpy(ruta_keras: Path) -> _ModeloLSTMNumpy | None:
    """Lee pesos del H5 dentro del ZIP .keras y construye el modelo NumPy."""
    try:
        import h5py
    except ImportError:
        log.error("h5py no instalado. Ejecuta: pip install h5py")
        return None

    try:
        with zipfile.ZipFile(ruta_keras, "r") as z:
            h5_data = z.read("model.weights.h5")

        with h5py.File(io.BytesIO(h5_data), "r") as f:
            # LSTM 1 (128 units)
            W1 = f["layers/lstm/cell/vars/0"][:]    # (5,   512)
            U1 = f["layers/lstm/cell/vars/1"][:]    # (128, 512)
            b1 = f["layers/lstm/cell/vars/2"][:]    # (512,)
            # LSTM 2 (64 units)
            W2 = f["layers/lstm_1/cell/vars/0"][:]  # (128, 256)
            U2 = f["layers/lstm_1/cell/vars/1"][:]  # (64,  256)
            b2 = f["layers/lstm_1/cell/vars/2"][:]  # (256,)
            # Dense (30 units)
            Wd = f["layers/dense/vars/0"][:]        # (64, 30)
            bd = f["layers/dense/vars/1"][:]        # (30,)

        return _ModeloLSTMNumpy(
            W1.astype(np.float32), U1.astype(np.float32), b1.astype(np.float32),
            W2.astype(np.float32), U2.astype(np.float32), b2.astype(np.float32),
            Wd.astype(np.float32), bd.astype(np.float32),
        )
    except Exception as e:
        log.warning("Error cargando pesos de {}: {}".format(ruta_keras.name, e))
        return None


# ── Clase principal ────────────────────────────────────────────────────────────
class PredictorLSTMGases:
    """Predictor LSTM por zona (inferencia NumPy, sin keras/tensorflow)."""

    def __init__(self) -> None:
        self._modelos:       dict = {}
        self._scalers:       dict = {}
        self._cargado:       bool = False
        self._modo_fallback: bool = False
        self._errores_carga: dict = {}

    # ── Carga ──────────────────────────────────────────────────────────────────
    def cargar(self) -> None:
        try:
            self._cargar_impl()
        except Exception as e:
            log.error("Error inesperado al cargar predictor: {}".format(e))
            self._modo_fallback = True

    def _cargar_impl(self) -> None:
        modelos_dir = Path(settings.model_paths.lstm_gases_dir)
        log.info("Cargando modelos LSTM (NumPy) desde: {}".format(modelos_dir))

        self._cargar_scalers()

        cargados = 0
        for zona in settings.zonas:
            nombre = "lstm_gases_{}.keras".format(zona)
            ruta   = modelos_dir / nombre

            if not ruta.exists():
                msg = "No encontrado: {}".format(ruta)
                self._errores_carga[zona] = msg
                log.warning("  " + msg)
                continue

            modelo = _cargar_modelo_numpy(ruta)
            if modelo is not None:
                self._modelos[zona] = modelo
                cargados += 1
                log.info("  Cargado (NumPy): {}".format(nombre))
            else:
                self._errores_carga[zona] = "Fallo al leer pesos H5"

        if cargados == 0:
            log.warning("Ningun modelo cargado — predictor en modo fallback.")
            self._modo_fallback = True
        else:
            self._cargado = True
            log.info("Predictor listo: {}/{} zonas".format(cargados, len(settings.zonas)))

    def _cargar_scalers(self) -> None:
        ruta = Path(settings.model_paths.lstm_scalers_gases)
        if not ruta.exists():
            log.info("Scaler pkl no encontrado — usando estadisticas por defecto.")
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                with open(ruta, "rb") as f:
                    data = pickle.load(f)
            scalers = data.get("scalers", data) if isinstance(data, dict) else {}
            for zona, sc in scalers.items():
                self._scalers[zona] = sc
            log.info("Scalers cargados: {}".format(list(self._scalers.keys())))
        except Exception as e:
            log.warning("Error cargando scalers: {} — usando stats por defecto.".format(e))

    # ── Normalizacion ──────────────────────────────────────────────────────────
    def _normalizar(self, historial: list, zona: str) -> np.ndarray:
        ventana  = settings.lstm_ventana
        hist     = historial[-ventana:]
        X_raw    = np.array([[h.get(g, 0.0) for g in FEATURES] for h in hist],
                            dtype=np.float32)
        scaler   = self._scalers.get(zona)
        if scaler is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return scaler.transform(X_raw).astype(np.float32)
            except Exception:
                pass
        return np.array([
            [(row[i] - GAS_STATS_DEFAULT[FEATURES[i]][0])
             / (GAS_STATS_DEFAULT[FEATURES[i]][1] + 1e-9)
             for i in range(len(FEATURES))]
            for row in X_raw
        ], dtype=np.float32)

    def _desnormalizar_paso(self, fila_norm: np.ndarray, zona: str) -> list:
        scaler = self._scalers.get(zona)
        if scaler is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    return scaler.inverse_transform(
                        fila_norm.reshape(1, -1))[0].tolist()
            except Exception:
                pass
        return [float(fila_norm[i] * GAS_STATS_DEFAULT[FEATURES[i]][1]
                      + GAS_STATS_DEFAULT[FEATURES[i]][0])
                for i in range(len(FEATURES))]

    # ── Prediccion ─────────────────────────────────────────────────────────────
    def predecir(self, historial: list, zona: str) -> dict:
        vacio = {"alertas_predictivas": [], "predicciones_crudas": []}

        if self._modo_fallback or not self._cargado:
            return vacio
        if zona not in self._modelos:
            return vacio
        if len(historial) < settings.lstm_ventana:
            return vacio

        try:
            ventana   = settings.lstm_ventana
            horizonte = settings.lstm_horizonte

            X_norm = self._normalizar(historial, zona)          # (ventana, 5)
            X      = X_norm.reshape(1, ventana, len(FEATURES))  # (1, 24, 5)

            pred_norm = self._modelos[zona].predict(X)          # (1, 6, 5)
            pred_norm = pred_norm[0]                            # (6, 5)

            n_pasos = min(pred_norm.shape[0], horizonte)
            pred_real = np.clip(
                np.array([self._desnormalizar_paso(pred_norm[t], zona)
                          for t in range(n_pasos)]),
                0, None
            )

            from backend.agentes.gases.umbrales import clasificar_gas
            alertas = []
            for t, paso in enumerate(pred_real):
                for i, gas in enumerate(FEATURES):
                    valor = float(paso[i])
                    nivel = clasificar_gas(gas, valor)
                    if NIVEL_ORDEN[nivel] >= NIVEL_ORDEN[NivelRiesgo.PRECAUCION]:
                        alertas.append({
                            "gas":            gas,
                            "valor_predicho": round(valor, 4),
                            "nivel":          nivel.value,
                            "horizonte_min":  (t + 1) * settings.lstm_min_por_paso,
                        })

            log.info("Prediccion OK para {}: {} pasos, {} alertas".format(
                zona, n_pasos, len(alertas)))

            return {
                "alertas_predictivas": alertas,
                "predicciones_crudas": pred_real.tolist(),
            }

        except Exception as e:
            log.warning("Error en prediccion para {}: {}".format(zona, e))
            return vacio
