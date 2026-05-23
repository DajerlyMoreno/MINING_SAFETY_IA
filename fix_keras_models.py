"""
fix_keras_models_v3.py — Instala dependencias faltantes automáticamente.
"""

import subprocess, sys

# ── Auto-instalar dependencias faltantes ─────────────────────────────────────
REQUERIDOS = [
    "scikit-learn",
    "pandas",
    "numpy",
]

def instalar_si_falta(paquete: str):
    try:
        __import__(paquete.replace("-", "_").split("==")[0])
    except ImportError:
        print(f"  📦 Instalando {paquete}...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", paquete],
            check=True
        )
        print(f"  ✅ {paquete} instalado")

print("🔍 Verificando dependencias...")
for dep in REQUERIDOS:
    instalar_si_falta(dep)
print("✅ Dependencias listas\n")

# ── Imports seguros (después de instalar) ────────────────────────────────────
import os, pickle, shutil
from pathlib import Path

import tensorflow as tf
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Versión de Keras (compatible con TF 2.15 y 2.16+)
try:
    keras_ver = tf.keras.__version__
except AttributeError:
    try:
        import keras; keras_ver = keras.__version__
    except Exception:
        keras_ver = "desconocida"

print(f"✅ TensorFlow: {tf.__version__}")
print(f"✅ Keras:      {keras_ver}")
print(f"✅ scikit-learn cargado correctamente")

# ── Rutas ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
MODELOS_DIR = BASE_DIR / "modelos"
REPARADOS   = BASE_DIR / "modelos_reparados"

ZONAS = [
    "Frente_A_Sogamoso",
    "Frente_B_Mongua",
    "Galeria_Central",
    "Bocamina",
]

# Arquitecturas (ajusta si difieren de tu entrenamiento en Colab)
GAS_VENTANA   = 24
GAS_HORIZONTE = 4
GAS_FEATURES  = 5   # CH4, CO, CO2, O2, H2S

GEO_VENTANA   = 12
GEO_HORIZONTE = 4
GEO_FEATURES  = 5   # deformacion, vibracion, presion, convergencia, estabilidad


# ════════════════════════════════════════════════════════════════════════════
# Constructores de modelos
# ════════════════════════════════════════════════════════════════════════════

def construir_lstm_gases():
    m = tf.keras.Sequential([
        tf.keras.layers.LSTM(32, return_sequences=True,
                             input_shape=(GAS_VENTANA, GAS_FEATURES)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.LSTM(16, return_sequences=False),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(GAS_HORIZONTE * GAS_FEATURES),
    ], name="lstm_gases")
    m.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return m


def construir_lstm_geo():
    m = tf.keras.Sequential([
        tf.keras.layers.LSTM(20, return_sequences=False,
                             input_shape=(GEO_VENTANA, GEO_FEATURES)),
        tf.keras.layers.Dropout(0.2),
        tf.keras.layers.Dense(GEO_HORIZONTE * GEO_FEATURES),
    ], name="lstm_geo")
    m.compile(optimizer="adam", loss="mse")
    return m


# ════════════════════════════════════════════════════════════════════════════
# Parche para cargar modelos con config de Keras 2.x en Keras 3.x
# ════════════════════════════════════════════════════════════════════════════

class _InputLayerCompat(tf.keras.layers.Layer):
    def __init__(self, batch_shape=None, dtype="float32",
                 sparse=False, ragged=False, name=None,
                 optional=False, **kwargs):
        super().__init__(name=name, dtype=dtype, **kwargs)
    def call(self, x): return x
    @classmethod
    def from_config(cls, cfg):
        cfg.pop("optional", None)
        cfg.pop("batch_input_shape", None)
        return cls(**cfg)


def _cargar_con_parche(ruta: Path):
    with tf.keras.utils.custom_object_scope({"InputLayer": _InputLayerCompat}):
        return tf.keras.models.load_model(str(ruta), compile=False)


# ════════════════════════════════════════════════════════════════════════════
# Reparar un modelo (transferir pesos)
# ════════════════════════════════════════════════════════════════════════════

def reparar(ruta_origen: Path, modelo_nuevo, ruta_destino: Path) -> bool:
    print(f"\n  📂 {ruta_origen.name}")

    for intento, (desc, fn) in enumerate([
        ("carga estándar",       lambda: tf.keras.models.load_model(str(ruta_origen), compile=False)),
        ("parche InputLayer",    lambda: _cargar_con_parche(ruta_origen)),
        ("safe_mode=False",      lambda: tf.keras.models.load_model(str(ruta_origen), compile=False, safe_mode=False)),
    ], 1):
        try:
            orig = fn()
            modelo_nuevo.set_weights(orig.get_weights())
            modelo_nuevo.save(str(ruta_destino))
            print(f"     ✅ [{desc}] pesos transferidos → {ruta_destino.name}")
            return True
        except Exception as e:
            print(f"     ⚠️  [{desc}] falló: {type(e).__name__}: {str(e)[:60]}")

    # Intento con .h5
    h5 = ruta_origen.with_suffix(".h5")
    if h5.exists():
        try:
            modelo_nuevo.load_weights(str(h5))
            modelo_nuevo.save(str(ruta_destino))
            print(f"     ✅ [pesos .h5] OK → {ruta_destino.name}")
            return True
        except Exception as e:
            print(f"     ⚠️  [pesos .h5] falló: {e}")

    print(f"     ❌ Todos los intentos fallaron → se reentrenará")
    return False


# ════════════════════════════════════════════════════════════════════════════
# Reentrenar desde CSV (sklearn ya disponible aquí)
# ════════════════════════════════════════════════════════════════════════════

def reentrenar(tipo: str):
    print(f"\n{'─'*60}")
    print(f"  🔄 Reentrenando {tipo.upper()} desde dataset CSV")
    print(f"{'─'*60}")

    csv = BASE_DIR / "datasets" / f"dataset_{tipo}.csv"
    if not csv.exists():
        # Buscar en otras ubicaciones comunes
        alternativas = [
            BASE_DIR / f"dataset_{tipo}.csv",
            BASE_DIR / "datasets" / f"dataset_gases_mineria.csv",
        ]
        for alt in alternativas:
            if alt.exists():
                csv = alt
                print(f"  📂 Usando: {csv}")
                break
        else:
            print(f"\n  ❌ No se encontró el dataset.")
            print(f"     Copia el archivo dataset_{tipo}.csv desde el ZIP de Colab a:")
            print(f"     {BASE_DIR / 'datasets' / f'dataset_{tipo}.csv'}")
            return {}

    print(f"  📊 Cargando {csv.name}...")
    df = pd.read_csv(csv)
    print(f"  Filas: {len(df):,} | Columnas: {list(df.columns)}")

    if tipo == "gases":
        cols     = ["CH4", "CO", "CO2", "O2", "H2S"]
        ven, hor = GAS_VENTANA, GAS_HORIZONTE
        destino  = REPARADOS / "gases"
        mk_model = construir_lstm_gases
        prefijo  = "lstm_gases"
    else:
        cols     = ["deformacion_mm", "vibracion_mms", "presion_kpa",
                    "convergencia_mm", "indice_estabilidad"]
        ven, hor = GEO_VENTANA, GEO_HORIZONTE
        destino  = REPARADOS / "geomecanico"
        mk_model = construir_lstm_geo
        prefijo  = "lstm_geo"

    # Verificar que las columnas existen
    faltantes = [c for c in cols if c not in df.columns]
    if faltantes:
        print(f"\n  ❌ Columnas faltantes en el dataset: {faltantes}")
        print(f"     Columnas disponibles: {list(df.columns)}")
        return {}

    destino.mkdir(parents=True, exist_ok=True)
    scalers = {}

    zonas_en_df = df["zona"].unique() if "zona" in df.columns else ["zona_unica"]

    for zona in zonas_en_df:
        print(f"\n  🏗️  Entrenando: {zona}")
        if "zona" in df.columns:
            X_raw = df[df["zona"] == zona][cols].values
        else:
            X_raw = df[cols].values

        if len(X_raw) < ven + hor + 10:
            print(f"     ⚠️  Datos insuficientes ({len(X_raw)} filas), se omite")
            continue

        sc = StandardScaler()
        Xs = sc.fit_transform(X_raw)
        scalers[zona] = sc

        seqs, tgts = [], []
        for i in range(len(Xs) - ven - hor):
            seqs.append(Xs[i : i + ven])
            tgts.append(Xs[i + ven : i + ven + hor].flatten())

        Xa, ya = np.array(seqs), np.array(tgts)
        sp = int(len(Xa) * 0.8)

        model = mk_model()
        cb = tf.keras.callbacks.EarlyStopping(
            patience=5, restore_best_weights=True, verbose=0
        )
        print(f"     Entrenando con {len(Xa[:sp])} secuencias...")
        hist = model.fit(
            Xa[:sp], ya[:sp],
            validation_data=(Xa[sp:], ya[sp:]),
            epochs=30, batch_size=64,
            callbacks=[cb], verbose=1,
        )

        nombre = f"{prefijo}_{zona}.keras"
        model.save(str(destino / nombre))
        best_loss = min(hist.history["val_loss"])
        print(f"     💾 Guardado: {nombre} | val_loss={best_loss:.5f}")

    # Guardar scalers
    sc_path = destino / f"lstm_scalers_{tipo}_nuevos.pkl"
    with open(sc_path, "wb") as f:
        pickle.dump(scalers, f)
    print(f"\n  💾 Scalers: {sc_path.name}")

    return scalers


# ════════════════════════════════════════════════════════════════════════════
# Reparar todos los modelos de una carpeta
# ════════════════════════════════════════════════════════════════════════════

def reparar_carpeta(tipo: str):
    label = "GASES" if tipo == "gases" else "GEOMECÁNICO"
    print(f"\n{'═'*60}")
    print(f"  🔧 AGENTE {label}")
    print(f"{'═'*60}")

    origen  = MODELOS_DIR / tipo
    destino = REPARADOS   / tipo
    destino.mkdir(parents=True, exist_ok=True)

    prefijo  = "lstm_gases" if tipo == "gases" else "lstm_geo"
    mk_model = construir_lstm_gases if tipo == "gases" else construir_lstm_geo

    exitosos, fallidos = [], []

    for zona in ZONAS:
        nombre = f"{prefijo}_{zona}.keras"
        src    = origen  / nombre
        dst    = destino / nombre

        if not src.exists():
            print(f"\n  ⏭️  No existe: {nombre}")
            continue

        if reparar(src, mk_model(), dst):
            exitosos.append(zona)
        else:
            fallidos.append(zona)

    # Copiar .pkl sin modificar
    for pkl in origen.glob("*.pkl"):
        shutil.copy(str(pkl), str(destino / pkl.name))
        print(f"\n  📋 Copiado: {pkl.name}")

    print(f"\n  ✅ Exitosos: {exitosos}")
    print(f"  ❌ Fallidos: {fallidos}")

    if fallidos:
        resp = input(f"\n  ¿Reentrenar {len(fallidos)} modelos fallidos desde dataset CSV? (s/N): ")
        if resp.strip().lower() == "s":
            reentrenar(tipo)

    return fallidos


# ════════════════════════════════════════════════════════════════════════════
# Verificar y aplicar
# ════════════════════════════════════════════════════════════════════════════

def verificar() -> bool:
    print(f"\n{'═'*60}")
    print("  🔍 VERIFICANDO MODELOS REPARADOS")
    print(f"{'═'*60}")
    ok = fail = 0
    for sub in ["gases", "geomecanico"]:
        carpeta = REPARADOS / sub
        if not carpeta.exists():
            continue
        print(f"\n  📁 {sub}/")
        for kf in sorted(carpeta.glob("*.keras")):
            try:
                m     = tf.keras.models.load_model(str(kf), compile=False)
                dummy = np.zeros([1] + list(m.input_shape[1:]))
                out   = m.predict(dummy, verbose=0)
                nparam = sum(int(tf.size(w)) for w in m.weights)
                print(f"     ✅ {kf.name:48s} in={m.input_shape} "
                      f"out={out.shape} params={nparam:,}")
                ok += 1
            except Exception as e:
                print(f"     ❌ {kf.name}: {e}")
                fail += 1
    print(f"\n  Resultado: {ok} OK — {fail} con error")
    return fail == 0


def aplicar():
    backup = MODELOS_DIR / "_backup"
    backup.mkdir(exist_ok=True)
    print(f"\n{'═'*60}")
    print("  🔄 REEMPLAZANDO ORIGINALES")
    print(f"{'═'*60}")
    for sub in ["gases", "geomecanico"]:
        bk = backup / sub; bk.mkdir(exist_ok=True)
        for kf in sorted((REPARADOS / sub).glob("*.keras")):
            orig = MODELOS_DIR / sub / kf.name
            if orig.exists():
                shutil.copy(str(orig), str(bk / kf.name))
            shutil.copy(str(kf), str(orig))
            print(f"  ✅ {kf.name}")
    print(f"\n  Backup en: {backup}")
    print("  Reinicia los servicios.")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  Fix Keras Models v3 — Minería UPTC 2026               ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    REPARADOS.mkdir(exist_ok=True)

    reparar_carpeta("gases")
    reparar_carpeta("geomecanico")

    if verificar():
        resp = input("\n¿Reemplazar originales con los reparados? (s/N): ")
        if resp.strip().lower() == "s":
            aplicar()
    else:
        print("\n  ⚠️  Revisa los errores arriba.")
        print("  Si el problema es la arquitectura, edita las constantes")
        print("  GAS_VENTANA, GAS_HORIZONTE, GAS_FEATURES al inicio del script.")
