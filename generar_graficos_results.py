"""
generar_graficos_results.py
Genera los gráficos PNG para la sección Results and Discussion del paper.

Gráficos generados:
  1. lstm_error_bar.png     — MAE y RMSE por gas (bar chart agrupado)
  2. niveles_riesgo_pie.png — Distribución de niveles de riesgo (pie chart)
  3. tipos_anomalia_bar.png — Breakdown por tipo de anomalía detectada (bar chart)
"""

import csv
import os
from collections import Counter

import matplotlib
matplotlib.use('Agg')  # sin interfaz, solo genera archivos
import matplotlib.pyplot as plt
import numpy as np

# ── Rutas ─────────────────────────────────────────────────────────────────────
CSV_PATH = os.path.join(os.path.dirname(__file__), "evaluacion_resultados.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "construccion-informe", "images")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Lectura del CSV ───────────────────────────────────────────────────────────
def leer_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

rows = leer_csv(CSV_PATH)
print(f"Ciclos leídos: {len(rows)}")

# ── 1. MAE / RMSE por gas ─────────────────────────────────────────────────────
GASES = ["CH4", "CO", "CO2", "O2", "H2S"]
FEATURES = ["real_CH4", "real_CO", "real_CO2", "real_O2", "real_H2S"]
PREDS_P1 = ["pred_CH4_p1", "pred_CO_p1", "pred_CO2_p1", "pred_O2_p1", "pred_H2S_p1"]

def calcular_mae_rmse(rows, real_cols, pred_cols):
    mae_vals, rmse_vals = [], []
    for r in rows:
        errores = []
        for real_col, pred_col in zip(real_cols, pred_cols):
            try:
                real = float(r[real_col])
                pred = float(r[pred_col])
                if real is not None and pred is not None:
                    errores.append(abs(real - pred))
            except (ValueError, TypeError, KeyError):
                pass
        if errores:
            mae_vals.append(np.mean(errores))
        else:
            mae_vals.append(0)
    # Para RMSE necesitamos la media de errores al cuadrado por gas
    mae_por_gas = []
    rmse_por_gas = []
    for real_col, pred_col in zip(real_cols, pred_cols):
        errores_gas = []
        for r in rows:
            try:
                real = float(r[real_col])
                pred = float(r[pred_col])
                if real is not None and pred is not None:
                    errores_gas.append(real - pred)
            except (ValueError, TypeError, KeyError):
                pass
        if errores_gas:
            mae_por_gas.append(np.mean([abs(e) for e in errores_gas]))
            rmse_por_gas.append(np.sqrt(np.mean([e**2 for e in errores_gas])))
        else:
            mae_por_gas.append(0)
            rmse_por_gas.append(0)
    return mae_por_gas, rmse_por_gas

mae_vals, rmse_vals = calcular_mae_rmse(rows, FEATURES, PREDS_P1)
print(f"MAE:  {list(zip(GASES, mae_vals))}")
print(f"RMSE: {list(zip(GASES, rmse_vals))}")

# ── 2. Distribución de niveles de riesgo ──────────────────────────────────────
niveles_counter = Counter(r["nivel_clasificado"] for r in rows)
NIVELES_ORDEN = ["SEGURO", "PRECAUCIÓN", "RIESGO ALTO", "EMERGENCIA", "EVACUACIÓN"]
niveles_vals = [niveles_counter.get(n, 0) for n in NIVELES_ORDEN]
print(f"Niveles: {dict(niveles_counter)}")

# ── 3. Tipos de anomalía ──────────────────────────────────────────────────────
tipos_counter = Counter(r["if_tipo"] for r in rows if r.get("if_detectado", "") == "True")
print(f"Tipos de anomalía: {dict(tipos_counter)}")

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICO 1 — MAE/RMSE por gas (bar chart agrupado)
# ══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(8, 5))
x = np.arange(len(GASES))
width = 0.35

bars_mae = ax.bar(x - width/2, mae_vals, width, label="MAE", color="#2E86AB", edgecolor="white")
bars_rmse = ax.bar(x + width/2, rmse_vals, width, label="RMSE", color="#A23B72", edgecolor="white")

ax.set_xlabel("Gas", fontsize=11)
ax.set_ylabel("Error (gas units)", fontsize=11)
ax.set_title("LSTM Prediction Error by Gas (500 cycles)", fontsize=13, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels([r"CH$_4$ (% vol.)", r"CO (ppm)", r"CO$_2$ (% vol.)",
                    r"O$_2$ (% vol.)", r"H$_2$S (ppm)"], fontsize=9)
ax.legend(fontsize=10)
ax.grid(axis="y", alpha=0.3)

# Etiquetas encima de las barras
for bar in bars_mae:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.05, f"{h:.3f}",
            ha="center", va="bottom", fontsize=7.5)
for bar in bars_rmse:
    h = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2, h + 0.05, f"{h:.3f}",
            ha="center", va="bottom", fontsize=7.5)

plt.tight_layout()
path1 = os.path.join(OUTPUT_DIR, "lstm_error_bar.png")
plt.savefig(path1, dpi=150)
plt.close()
print(f"Guardado: {path1}")

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICO 2 — Distribución de niveles de riesgo (pie chart)
# ══════════════════════════════════════════════════════════════════════════════
# Solo los que tienen valor > 0 para que el pie chart sea legible
niveles_no_cero = [(n, v) for n, v in zip(NIVELES_ORDEN, niveles_vals) if v > 0]
# Etiquetas en ingles
labels_en = {"SEGURO": "SAFE", "PRECAUCION": "CAUTION", "RIESGO ALTO": "HIGH RISK",
             "EMERGENCIA": "EMERGENCY", "EVACUACION": "EVACUATION"}
labels = [f"{labels_en.get(n, n)}\n{v} cycles ({v/sum(niveles_vals)*100:.1f}%)" for n, v in niveles_no_cero]
sizes = [v for _, v in niveles_no_cero]
colors = ["#28A745", "#FFC107", "#FF5733", "#DC3545", "#7B1FA2"]
explode = [0.02] * len(sizes)

fig, ax = plt.subplots(figsize=(7, 7))
wedges, texts = ax.pie(
    sizes,
    explode=explode,
    labels=labels,
    colors=colors[:len(sizes)],
    startangle=90,
    textprops={"fontsize": 10},
)
for w in wedges:
    w.set_edgecolor("white")
    w.set_linewidth(1.5)

ax.set_title("Risk Level Distribution\n(500 cycles)", fontsize=13, fontweight="bold")
plt.tight_layout()
path2 = os.path.join(OUTPUT_DIR, "niveles_riesgo_pie.png")
plt.savefig(path2, dpi=150)
plt.close()
print(f"Guardado: {path2}")

# ══════════════════════════════════════════════════════════════════════════════
# GRÁFICO 3 — Tipos de anomalía detectadas (horizontal bar chart)
# ══════════════════════════════════════════════════════════════════════════════
tipos_labels = list(tipos_counter.keys())
tipos_counts = list(tipos_counter.values())
# English labels
tipos_labels_en = {
    "patron_multivariado": "Multivariate pattern",
    "patron_incendio":     "Fire pattern",
    "incremento_brusco":   "Abrupt increase",
}
tipos_labels_display = [tipos_labels_en.get(t, t) for t in tipos_labels]

fig, ax = plt.subplots(figsize=(7, 5))
y = np.arange(len(tipos_labels_display))
bars = ax.barh(y, tipos_counts, color="#2E86AB", edgecolor="white")

ax.set_yticks(y)
ax.set_yticklabels(tipos_labels_display, fontsize=10)
ax.set_xlabel("Number of cycles detected", fontsize=11)
ax.set_title("Anomaly Types Detected by Isolation Forest\n(368 cycles with positive detection)", fontsize=12, fontweight="bold")
ax.grid(axis="x", alpha=0.3)

for bar, count in zip(bars, tipos_counts):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f"{count} ({count/sum(tipos_counts)*100:.1f}%)",
            va="center", fontsize=9)

plt.tight_layout()
path3 = os.path.join(OUTPUT_DIR, "tipos_anomalia_bar.png")
plt.savefig(path3, dpi=150)
plt.close()
print(f"Guardado: {path3}")

print("\n✅ Gráficos generados exitosamente.")
print(f"   Ubicación: {OUTPUT_DIR}")