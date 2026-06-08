"""
evaluacion_sistema.py — Script de evaluación headless para Results & Discussion.

Uso:
  1. Arrancar el sistema con start_system.bat
  2. python evaluacion_sistema.py

Qué hace:
  1. Espera a que los servicios (Orquestador 8007, Agente Gases 8001) estén disponibles
  2. Corre N ciclos (default: 200) alternando entre las 4 zonas
  3. Captura por ciclo: lectura real, predicción LSTM, detección IF, nivel clasificado
  4. Calcula MAE, RMSE, tasa de detección, falsos positivos
  5. Guarda resultados en evaluacion_resultados.csv
"""

import asyncio
import csv
import time
from datetime import datetime
from pathlib import Path
import os

import httpx
import numpy as np

# ── Constantes ────────────────────────────────────────────────────────────────
ZONAS = ["Frente_A_Sogamoso", "Frente_B_Mongua", "Galeria_Central", "Bocamina"]
N_CICLOS = 500
INTERVALO_SEG = 1  # rápido para evaluación (no 15 seg del simulador real)
OUTPUT_CSV = Path("evaluacion_resultados.csv")

FEATURES = ["CH4", "CO", "CO2", "O2", "H2S"]


def esperar_servicio(url: str, timeout: int = 30) -> bool:
    """Espera hasta que un servicio esté disponible."""
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            r = httpx.get(f"{url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    print(f"  Timeout esperando {url}")
    return False


async def capturar_ciclo(client: httpx.AsyncClient, zona: str, ciclo: int) -> dict:
    """
    Captura un ciclo completo de evaluación:
    1. Obtiene datos crudos del simulador (sensores)
2. Envía al Agente de Gases para análisis
    3. Extrae métricas: lectura real, predicción LSTM, detección IF, nivel
    """
    try:
        # Paso 1: Obtener datos crudos del simulador
        resp_sensores = await client.get(
            f"http://127.0.0.1:8005/sensores/gases/{zona}",
            timeout=5.0
        )
        if resp_sensores.status_code != 200:
            return {"ciclo": ciclo, "zona": zona, "error": f"Sensores HTTP {resp_sensores.status_code}"}

        sensores = resp_sensores.json()
        # El endpoint /sensores/gases/{zona} devuelve los valores directamente en la respuesta
        gases = sensores # directamente los valores del sensor

        # Paso 2: Enviar al Agente de Gases para análisis completo
        payload = {
            "zona": zona,
            "CH4": gases.get("CH4", 0),
            "CO": gases.get("CO", 0),
            "CO2": gases.get("CO2", 0),
            "O2": gases.get("O2", 20.9),
            "H2S": gases.get("H2S", 0),
            "temperatura_C": gases.get("temperatura", 22),
            "humedad_pct": gases.get("humedad", 65),
        }
        resp_analisis = await client.post(
            "http://127.0.0.1:8001/analizar",
            json=payload,
            timeout=10.0
        )
        if resp_analisis.status_code != 200:
            return {"ciclo": ciclo, "zona": zona, "error": f"Analisis HTTP {resp_analisis.status_code}"}

        analisis = resp_analisis.json()

        # Extraer datos del análisis
        resultado = {
            "ciclo": ciclo,
            "zona": zona,
            "timestamp": datetime.now().isoformat(),
            "nivel_clasificado": analisis.get("nivel_riesgo", "?"),
            "es_alerta": analisis.get("nivel_riesgo") in ("EMERGENCIA", "EVACUACION"),
        }

        # Datos de gases actuales (reales)
        for gas in FEATURES:
            resultado[f"real_{gas}"] = gases.get(gas, None)

        # Predicciones LSTM (próximos 6 pasos)
        predicciones = analisis.get("predicciones", [])
        for i, pred in enumerate(predicciones[:6]):
            gases_pred = pred.get("gases_predichos", {})
            for gas in FEATURES:
                resultado[f"pred_{gas}_p{i+1}"] = gases_pred.get(gas, None)

        # Detección de anomalías
        anomalia = analisis.get("anomalia", {})
        resultado["if_score"] = anomalia.get("score_anomalia", 0.0)
        resultado["if_detectado"] = anomalia.get("es_anomalia", False)
        resultado["if_tipo"] = anomalia.get("tipo_anomalia", "")

        return resultado

    except Exception as e:
        return {"ciclo": ciclo, "zona": zona, "error": str(e)}


def calcular_metricas(resultados: list):
    """Calcula y muestra las métricas de evaluación."""
    print("\n" + "=" * 50)
    print("MÉTRICAS DE EVALUACIÓN")
    print("=" * 50)

    # Filtrar ciclos sin errores
    ciclos = [r for r in resultados if "error" not in r]
    if not ciclos:
        print("No hay datos válidos para calcular métricas.")
        errores = [r for r in resultados if "error" in r]
        print(f"\nDebug: {len(errores)} ciclos con error")
        if errores[:3]:
            print("Ejemplo de error:", errores[0])
        return

    n_ciclos = len(ciclos)
    n_alertas = sum(1 for r in ciclos if r.get("es_alerta"))
    n_if_detectadas = sum(1 for r in ciclos if r.get("if_detectado"))

    print(f"\nCiclos evaluados: {n_ciclos}")
    print(f"Alertas emitidas (EMERGENCIA/EVACUACIÓN): {n_alertas} ({n_alertas/n_ciclos*100:.1f}%)")
    print(f"Detecciones Isolation Forest: {n_if_detectadas} ({n_if_detectadas/n_ciclos*100:.1f}%)")

    # MAE y RMSE por gas (predicción vs real — comparando con paso 1 = 15 min)
    print("\n--- Error de Predicción LSTM (MAE / RMSE) ---")
    for gas in FEATURES:
        errores = []
        for r in ciclos:
            real = r.get(f"real_{gas}")
            pred = r.get(f"pred_{gas}_p1")
            if real is not None and pred is not None:
                try:
                    errores.append(abs(float(real) - float(pred)))
                except (ValueError, TypeError):
                    pass
        if errores:
            mae = np.mean(errores)
            rmse = np.sqrt(np.mean([e**2 for e in errores]))
            print(f"  {gas}: MAE={mae:.4f}, RMSE={rmse:.4f} (n={len(errores)})")

    # Isolation Forest: score promedio
    scores = [r.get("if_score", 0) for r in ciclos if r.get("if_score")]
    if scores:
        print(f"\n--- Isolation Forest ---")
        print(f"  Score promedio: {np.mean(scores):.4f}")
        print(f"  Score máximo: {np.max(scores):.4f}")
        print(f"  Score mínimo: {np.min(scores):.4f}")
        print(f"  Detecciones activas: {n_if_detectadas}/{n_ciclos} ({n_if_detectadas/n_ciclos*100:.1f}%)")

    # Distribución de niveles
    print("\n--- Distribución de Niveles ---")
    niveles = {}
    for r in ciclos:
        niv = r.get("nivel_clasificado", "?")
        niveles[niv] = niveles.get(niv, 0) + 1
    for niv, count in sorted(niveles.items(), key=lambda x: -x[1]):
        print(f"  {niv}: {count} ({count/n_ciclos*100:.1f}%)")


async def ejecutar_evaluacion():
    """Ciclo principal de evaluación."""
    print(f"=== Evaluación del Sistema — {N_CICLOS} ciclos ===")

    # Esperar que los servicios estén disponibles
    print("Esperando servicios...")
    if not esperar_servicio("http://127.0.0.1:8007"):
        print("ERROR: Orquestador no disponible en puerto 8007")
        print("       Arrancá el sistema con start_system.bat primero")
        return
    if not esperar_servicio("http://127.0.0.1:8001"):
        print("ERROR: Agente de Gases no disponible en puerto 8001")
        return
    print("Servicios listos. Comenzando evaluación...\n")

    resultados = []

    async with httpx.AsyncClient() as client:
        for ciclo in range(1, N_CICLOS + 1):
            zona = ZONAS[ciclo % len(ZONAS)]
            r = await capturar_ciclo(client, zona, ciclo)
            resultados.append(r)

            if ciclo % 20 == 0:
                print(f"  Progreso: {ciclo}/{N_CICLOS} ciclos completados")

            await asyncio.sleep(INTERVALO_SEG)

    # Guardar CSV
    if resultados:
        columnas = (
            ["ciclo", "zona", "timestamp", "nivel_clasificado", "es_alerta",
             "if_score", "if_detectado", "if_tipo"]
            + [f"real_{g}" for g in FEATURES]
            + [f"pred_{g}_p{p}" for g in FEATURES for p in range(1, 7)]
        )

        with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(resultados)

        print(f"\nCSV guardado en: {OUTPUT_CSV.absolute()}")

    # Calcular e imprimir métricas
    calcular_metricas(resultados)


if __name__ == "__main__":
    asyncio.run(ejecutar_evaluacion())
