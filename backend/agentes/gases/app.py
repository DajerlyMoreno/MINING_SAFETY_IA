"""
app.py — FastAPI del Agente de Gases (Puerto 8001).
Expone endpoints para análisis de lecturas, predicción y consulta RAG.
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.shared.config import settings
from backend.shared.enums import NivelRiesgo, NIVEL_ORDEN
from backend.shared.logger import get_logger
from backend.agentes.gases.umbrales import clasificar_gas, UMBRALES_GAS
from backend.agentes.gases.anomaly_detector import AnomalyDetector
from backend.agentes.gases.predictor import PredictorLSTMGases
from backend.rag.rag_engine import rag
from backend.shared.database import inicializar_db, cargar_historial, guardar_lectura, limpiar_historial

log = get_logger("agente_gases")

# ── Estado del agente ─────────────────────────────────────────────────────────
detector  = AnomalyDetector()
predictor = PredictorLSTMGases()
historial: dict[str, list[dict]] = {z: [] for z in settings.zonas}
FEATURES  = ["CH4", "CO", "CO2", "O2", "H2S"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialización y apagado del agente."""
    log.info("=== Iniciando Agente de Gases ===")
    # Persistencia SQLite
    inicializar_db()
    for zona in settings.zonas:
        datos = await cargar_historial(zona, n=500)
        if datos:
            historial[zona] = datos
            log.info(f"  [{zona}] {len(datos)} lecturas cargadas desde SQLite")
    detector.cargar()
    predictor.cargar()
    rag.inicializar()
    log.info("Agente de Gases listo en puerto 8001")
    yield
    log.info("=== Agente de Gases detenido ===")


app = FastAPI(
    title="🧪 Agente de Gases — Minería Subterránea UPTC 2026",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Schemas ───────────────────────────────────────────────────────────────────
class LecturaGasRequest(BaseModel):
    zona: str              = Field(example="Frente_A_Sogamoso")
    CH4:  float            = Field(ge=0,    example=0.8)
    CO:   float            = Field(ge=0,    example=15.0)
    CO2:  float            = Field(ge=0,    example=0.2)
    O2:   float            = Field(ge=0, le=25, example=20.8)
    H2S:  float            = Field(ge=0,    example=0.3)
    temperatura_C: float   = Field(default=22.0)
    humedad_pct:   float   = Field(default=75.0)


class AnalisisResponse(BaseModel):
    timestamp:          str
    zona:               str
    nivel_riesgo:       str
    gases_criticos:     list[dict]
    anomalia:           dict
    predicciones:       list[dict]
    acciones:           list[str]
    normativa:          list[str]
    explicacion:        str
    confianza:          float


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "agente":    "AGENTE_GASES",
        "estado":    "ACTIVO",
        "timestamp": datetime.utcnow().isoformat(),
        "zonas":     list(settings.zonas),
    }


@app.post("/analizar", response_model=AnalisisResponse)
async def analizar(req: LecturaGasRequest):
    """Analiza una lectura de sensores y retorna diagnóstico completo."""
    if req.zona not in settings.zonas:
        raise HTTPException(400, f"Zona no soportada: {req.zona}")

    lectura = {g: getattr(req, g) for g in FEATURES}
    lectura["temperatura"] = req.temperatura_C
    lectura["humedad"]     = req.humedad_pct

    # 1) Clasificar por umbrales
    gases_criticos = []
    nivel_global = NivelRiesgo.SEGURO
    for gas in FEATURES:
        nivel = clasificar_gas(gas, lectura[gas])
        if nivel != NivelRiesgo.SEGURO:
            u = UMBRALES_GAS[gas]
            gases_criticos.append({
                "gas":    gas, "nombre": u.nombre,
                "valor":  lectura[gas], "unidad": u.unidad,
                "nivel":  nivel.value,
                "norma":  u.articulo_decreto,
            })
            if NIVEL_ORDEN[nivel] > NIVEL_ORDEN[nivel_global]:
                nivel_global = nivel

    # 1b) Clasificar temperatura y humedad (no entran al LSTM, solo a umbrales)
    for var, valor in [("temperatura", req.temperatura_C), ("humedad", req.humedad_pct)]:
        if var in UMBRALES_GAS:
            nivel = clasificar_gas(var, valor)
            if nivel != NivelRiesgo.SEGURO:
                u = UMBRALES_GAS[var]
                gases_criticos.append({
                    "gas":    var, "nombre": u.nombre,
                    "valor":  valor, "unidad": u.unidad,
                    "nivel":  nivel.value,
                    "norma":  u.articulo_decreto,
                })
                if NIVEL_ORDEN[nivel] > NIVEL_ORDEN[nivel_global]:
                    nivel_global = nivel

    # 2) Detección de anomalías
    hist_list = historial[req.zona]
    anomalia = detector.detectar(lectura, req.zona, hist_list[-50:] if hist_list else None)

    # Estrategia de elevación por anomalía — tres categorías:
    #  1. Críticas determinísticas: elevan siempre (sensor roto, incendio, explosividad)
    #  2. Incremento brusco: eleva con historial suficiente (señal real, no ruido)
    #  3. Patrón multivariado (IsolationForest): requiere score ALTO + historial suficiente
    #     + al menos un gas en zona de vigilancia (>= 40% umbral PRECAUCIÓN).
    #     Sin este último filtro, el IsolationForest genera PRECAUCIÓN perpetua para zonas
    #     de baseline bajo (ej. Bocamina) donde valores 3× su media son técnicamente seguros.
    _MIN_HIST_ANOMALIA = 20
    _SCORE_MINIMO_IF   = 0.62
    _ANOMALIAS_CRITICAS = {"falla_sensor", "patron_incendio", "zona_explosividad"}
    _UMBRALES_VIGIL = {"CH4": 0.5, "CO": 25.0, "CO2": 0.5, "H2S": 1.0}
    _FRAC_VIGIL     = 0.40   # 40% del umbral PRECAUCIÓN

    tipo_an  = anomalia.get("tipo_anomalia")
    score_an = anomalia.get("score_anomalia", 0.0)

    # ¿Algún gas está en zona de vigilancia (>= 40 % del umbral)?
    gas_en_vigilancia = any(
        getattr(req, g, 0.0) >= u * _FRAC_VIGIL
        for g, u in _UMBRALES_VIGIL.items()
    )

    if anomalia["es_anomalia"] and nivel_global == NivelRiesgo.SEGURO:
        if tipo_an in _ANOMALIAS_CRITICAS:
            nivel_global = NivelRiesgo.PRECAUCION
        elif tipo_an == "incremento_brusco" and len(hist_list) >= _MIN_HIST_ANOMALIA:
            nivel_global = NivelRiesgo.PRECAUCION
        elif (tipo_an == "patron_multivariado"
              and score_an >= _SCORE_MINIMO_IF
              and len(hist_list) >= _MIN_HIST_ANOMALIA
              and gas_en_vigilancia):
            nivel_global = NivelRiesgo.PRECAUCION

    # 3) Predicción LSTM
    predicciones_alertas = []
    if len(hist_list) >= settings.lstm_ventana:
        try:
            
            pred = predictor.predecir(hist_list, req.zona)

            # Construir pasos completos: gases_predichos + nivel_predicho + alertas
            crudas = pred.get("predicciones_crudas", [])
            alertas_por_paso: dict[int, list] = {}
            for a in pred.get("alertas_predictivas", []):
                t = a["horizonte_min"] // settings.lstm_min_por_paso - 1
                alertas_por_paso.setdefault(t, []).append(a["gas"])

            pasos_completos = []
            for t, fila in enumerate(crudas):
                gases_pred = {g: round(float(max(0, fila[i])), 4)
                              for i, g in enumerate(FEATURES)}
                # nivel predicho para ese paso — con margen para evitar falsos positivos
                # cerca del umbral (mismo margen que usa predictor.py en alertas_predictivas)
                _MARGEN_P = {"CH4": 1.15, "CO": 1.10, "CO2": 1.15, "H2S": 1.20}
                _MARGEN_O2 = 0.5
                nivel_paso = NivelRiesgo.SEGURO
                for g, v in gases_pred.items():
                    v_eval = (v + _MARGEN_O2) if g == "O2" else (v / _MARGEN_P.get(g, 1.15))
                    nv = clasificar_gas(g, v_eval)
                    if NIVEL_ORDEN[nv] > NIVEL_ORDEN[nivel_paso]:
                        nivel_paso = nv
                pasos_completos.append({
                    "paso":          t + 1,
                    "horizonte_min": (t + 1) * settings.lstm_min_por_paso,
                    "gases_predichos": gases_pred,
                    "nivel_predicho":  nivel_paso.value,
                    "alertas":         alertas_por_paso.get(t, []),
                })

            predicciones_alertas = pasos_completos
        except Exception as e:
            log.warning(f"Predicción fallida para {req.zona}: {e}")

    # 4) RAG
    nombres_gases_criticos = [g["gas"] for g in gases_criticos]
    docs_rag = rag.consultar_por_nivel_y_gases(nombres_gases_criticos, nivel_global.value)
    normativa = [d["titulo"] for d in docs_rag]

    # 5) Acciones
    ACCIONES = {
        NivelRiesgo.SEGURO:      ["Monitoreo rutinario continuo"],
        NivelRiesgo.INFORMATIVO: ["Registrar lectura", "Verificar tendencia"],
        NivelRiesgo.PRECAUCION:  ["Notificar jefe de turno", "Aumentar ventilación",
                                   "Preparar auto-rescatadores"],
        NivelRiesgo.RIESGO_ALTO: ["SUSPENDER ACTIVIDADES", "Evacuar frente",
                                   "Activar ventilación de emergencia", "Reportar a ANM"],
        NivelRiesgo.EMERGENCIA:  ["EVACUACIÓN PARCIAL", "Cortar equipos no ATEX",
                                   "Activar brigada de rescate"],
        NivelRiesgo.EVACUACION:  ["🚨 EVACUACIÓN TOTAL INMEDIATA",
                                   "Activar alarma general (3 pitidos + 1 largo)",
                                   "Llamar 123 — ANM: 57-1-3199099"],
    }
    acciones = ACCIONES.get(nivel_global, [])
    tipo_an = anomalia.get("tipo_anomalia")
    if tipo_an == "falla_sensor":
        acciones = ["🔧 VERIFICAR SENSOR DEFECTUOSO"] + acciones
    elif tipo_an == "patron_incendio":
        acciones = ["🔥 ACTIVAR PROTOCOLO ANTI-INCENDIO — identificar fuente de calor",
                    "Cortar equipos no ATEX en la zona"] + acciones
    elif tipo_an == "zona_explosividad":
        acciones = ["💥 ZONA EXPLOSIVA — eliminar fuentes de ignición",
                    "Evacuar y ventilar hasta CH4 < 1 % vol."] + acciones

    # 6) Guardar en historial (máx 500 por zona) y persistir en SQLite
    hist_list.append(lectura)
    if len(hist_list) > 500:
        hist_list.pop(0)
    await guardar_lectura(req.zona, lectura)

    gases_str = "; ".join(f"{g['gas']}={g['valor']:.3f}{g['unidad']}" for g in gases_criticos)

    tendencias   = anomalia.get("tendencias", {})
    subiendo     = [g for g, s in tendencias.items() if s >  0.001]
    bajando      = [g for g, s in tendencias.items() if s < -0.001]
    trend_str    = ""
    if subiendo:
        trend_str += f" Subiendo: {', '.join(subiendo)}."
    if bajando:
        trend_str += f" Bajando: {', '.join(bajando)}."

    explicacion = (
        f"Gases críticos: {gases_str or 'ninguno'}. "
        f"{'Anomalía: ' + anomalia['tipo_anomalia'] + '. ' if anomalia['es_anomalia'] else ''}"
        f"{len(predicciones_alertas)} alertas predictivas activas."
        f"{trend_str}"
    )

    score_if  = anomalia.get("score_anomalia", 0.0)
    confianza = round(max(0.50, 0.95 - score_if * 0.25), 2)

    return AnalisisResponse(
        timestamp=datetime.utcnow().isoformat(),
        zona=req.zona,
        nivel_riesgo=nivel_global.value,
        gases_criticos=gases_criticos,
        anomalia=anomalia,
        predicciones=predicciones_alertas,
        acciones=acciones,
        normativa=normativa,
        explicacion=explicacion,
        confianza=confianza,
    )


# Valores de linea base por zona — condiciones normales SEGURO (Decreto 1886/2015)
_LINEA_BASE: dict[str, dict] = {
    "Frente_A_Sogamoso": {"CH4": 0.18, "CO": 4.5,  "CO2": 0.10, "O2": 20.65, "H2S": 0.18},
    "Frente_B_Mongua":   {"CH4": 0.14, "CO": 3.2,  "CO2": 0.08, "O2": 20.75, "H2S": 0.12},
    "Galeria_Central":   {"CH4": 0.10, "CO": 2.8,  "CO2": 0.07, "O2": 20.80, "H2S": 0.09},
    "Bocamina":          {"CH4": 0.06, "CO": 1.5,  "CO2": 0.05, "O2": 20.90, "H2S": 0.05},
}
_N_LECTURAS_INICIALES = 10


@app.post("/reset")
async def reset_historial():
    """Borra el historial y precarga 10 lecturas en condiciones SEGURO (linea base).
    Esto permite que el dashboard muestre datos inmediatamente y el LSTM
    acumule contexto desde el primer ciclo real."""
    import random, math

    borradas = await limpiar_historial()

    insertadas = 0
    for zona in settings.zonas:
        base = _LINEA_BASE.get(zona, _LINEA_BASE["Bocamina"])
        lecturas_zona = []
        for i in range(_N_LECTURAS_INICIALES):
            # Pequeña variacion aleatoria (~3%) para que no sean identicas
            lectura = {
                g: round(v * (1.0 + random.uniform(-0.03, 0.03)), 4)
                for g, v in base.items()
            }
            lecturas_zona.append(lectura)
            await guardar_lectura(zona, lectura)
            insertadas += 1
        historial[zona] = lecturas_zona

    log.info(
        f"Historial reiniciado: {borradas} borradas, "
        f"{insertadas} lecturas base insertadas ({_N_LECTURAS_INICIALES} por zona)"
    )
    return {
        "estado":            "reiniciado",
        "lecturas_borradas": borradas,
        "lecturas_base":     insertadas,
        "zonas":             list(settings.zonas),
    }


@app.get("/historial/{zona}")
async def obtener_historial(zona: str, n: int = 50):
    """Retorna las últimas N lecturas de una zona."""
    if zona not in historial:
        raise HTTPException(404, f"Zona {zona} no encontrada")
    return {"zona": zona, "lecturas": historial[zona][-n:]}


@app.post(
    "/ciclo/{zona}",
    summary="Ciclo autónomo — recolecta del simulador, procesa y entrega",
    description=(
        "El agente actúa de forma autónoma: "
        "1. Lee los valores crudos del sensor de gases desde el simulador. "
        "2. Aplica umbrales Decreto 1886/2015, LSTM y detección de anomalías. "
        "3. Retorna el análisis procesado listo para el orquestador. "
        "Este endpoint implementa el flujo correcto donde el agente RECOLECTA "
        "su información del sensor y la procesa antes de pasarla a la siguiente capa."
    ),
)
async def ciclo_autonomo(zona: str):
    """
    Flujo correcto: Agente Gases recolecta sensor → procesa → entrega resultado.
    Llama al simulador en /sensores/gases/{zona} para obtener datos crudos.
    """
    import httpx
    from backend.shared.config import settings

    sim_url = f"http://{settings.simulador.host}:{settings.simulador.port}/sensores/gases/{zona}"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(sim_url)
            resp.raise_for_status()
            datos = resp.json()
    except Exception as e:
        raise HTTPException(503, f"Simulador no disponible: {e}")

    # Construir request con los datos crudos del sensor y procesar
    req = LecturaGasRequest(
        zona=zona,
        CH4=datos.get("CH4", 0.0),
        CO= datos.get("CO",  0.0),
        CO2=datos.get("CO2", 0.0),
        O2= datos.get("O2",  20.9),
        H2S=datos.get("H2S", 0.0),
        temperatura_C=datos.get("temperatura", 22.0),
        humedad_pct=datos.get("humedad", 65.0),
    )
    return await analizar(req)


@app.get("/predictor/status")
async def predictor_status():
    """Diagnóstico del predictor LSTM: modelos cargados, scalers, modo, rutas."""
    try:
        modelos_dir = settings.model_paths.lstm_gases_dir
        scaler_path = settings.model_paths.lstm_scalers_gases

        modelos_en_disco = {}
        for zona in settings.zonas:
            nombre = "lstm_gases_{}.keras".format(zona)
            ruta = modelos_dir / nombre
            modelos_en_disco[zona] = str(ruta) if ruta.exists() else "NO ENCONTRADO: {}".format(ruta)

        # Detectar backends disponibles
        backends = {}
        for pkg in ["tensorflow", "tf_keras", "keras"]:
            try:
                mod = __import__(pkg)
                backends[pkg] = getattr(mod, "__version__", "instalado")
            except Exception as e:
                backends[pkg] = "ERROR: {}".format(str(e)[:120])

        return {
            "predictor": {
                "cargado":        getattr(predictor, "_cargado",       False),
                "modo_fallback":  getattr(predictor, "_modo_fallback", True),
                "modelos_en_ram": list(getattr(predictor, "_modelos", {}).keys()),
                "scalers_en_ram": list(getattr(predictor, "_scalers", {}).keys()),
                "errores_carga":  getattr(predictor, "_errores_carga", {}),
            },
            "rutas": {
                "lstm_gases_dir":    str(modelos_dir),
                "lstm_gases_existe": modelos_dir.exists(),
                "scaler_path":       str(scaler_path),
                "scaler_existe":     scaler_path.exists(),
            },
            "modelos_en_disco": modelos_en_disco,
            "backends_python":  backends,
            "historial_lecturas": {z: len(h) for z, h in historial.items()},
        }
    except Exception as e:
        return {"error": str(e), "tipo": type(e).__name__}