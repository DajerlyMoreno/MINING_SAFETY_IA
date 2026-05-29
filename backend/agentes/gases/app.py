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
from backend.shared.database import inicializar_db, cargar_historial, guardar_lectura

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

    # 2) Detección de anomalías
    hist_list = historial[req.zona]
    anomalia = detector.detectar(lectura, req.zona, hist_list[-50:] if hist_list else None)

    if anomalia["es_anomalia"] and nivel_global == NivelRiesgo.SEGURO:
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
                # nivel predicho para ese paso
                nivel_paso = NivelRiesgo.SEGURO
                for g, v in gases_pred.items():
                    nv = clasificar_gas(g, v)
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
    if anomalia.get("tipo_anomalia") == "falla_sensor":
        acciones = ["🔧 VERIFICAR SENSOR DEFECTUOSO"] + acciones

    # 6) Guardar en historial (máx 500 por zona) y persistir en SQLite
    hist_list.append(lectura)
    if len(hist_list) > 500:
        hist_list.pop(0)
    await guardar_lectura(req.zona, lectura)

    gases_str = "; ".join(f"{g['gas']}={g['valor']:.3f}{g['unidad']}" for g in gases_criticos)
    explicacion = (
        f"Gases críticos: {gases_str or 'ninguno'}. "
        f"{'Anomalía: ' + anomalia['tipo_anomalia'] + '. ' if anomalia['es_anomalia'] else ''}"
        f"{len(predicciones_alertas)} alertas predictivas activas."
    )

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
        confianza=0.93 if not anomalia["es_anomalia"] else 0.75,
    )


@app.get("/historial/{zona}")
async def obtener_historial(zona: str, n: int = 50):
    """Retorna las últimas N lecturas de una zona."""
    if zona not in historial:
        raise HTTPException(404, f"Zona {zona} no encontrada")
    return {"zona": zona, "lecturas": historial[zona][-n:]}


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