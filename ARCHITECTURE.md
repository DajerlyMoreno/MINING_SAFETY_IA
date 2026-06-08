# 🏗️ Arquitectura — MINING_SAFETY_IA

> Sistema multiagente de monitoreo para minería subterránea con IA.
> Este documento describe la arquitectura, los agentes y cómo se comunican.

---

## Vista General del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DASHBOARD (React) │
│                         http://localhost:3000                               │
│                    WebSocket /ws/eventos + HTTP REST │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │ WebSocket broadcast
                                    │ HTTP REST
┌────────────────────────────────────┴─────────────────────────────────────┐
│ ORQUESTADOR (Puerto 8007)                                                │
│  FastAPI — Punto de entrada central                                      │
│  ├── Coordina todos los agentes                                          │
│  ├── Correlaciona análisis de múltiples fuentes                          │
│  ├── Integra LLM (Gemini) + RAG                                          │
│  ├── Mantiene historial de eventos                                       │
│  └── Broadcast a dashboard via WebSocket                                 │
└─────────────────────────────────────────────────────────────────────────────┘
          │                          │                                                       │
          │ HTTP REST          │ HTTP REST                │ HTTP REST
          ▼                           ▼                           ▼
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  AGENTE GASESES  │      │ AGENTE GEOMECÁNICO│ │ AGENTE IMÁGENES  │
│   (Puerto 8001)  │      │   (Puerto 8003)  │      │   (Puerto 8002)  │
│                  │      │   [No activo]    │      │   [No activo]    │
│ • LSTM predictor │      │                  │      │                  │
│ • Isolation Forest│     │                  │      │                  │
│ • Anomaly detection│ │                  │      │                  │
└────────┬─────────┘      └─────────────────┘      └─────────────────┘
         │
         │ HTTP GET /sensores/gases/{zona}
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SIMULADOR (Puerto 8005)                              │
│  Genera datos sintéticos de sensores de gases │
│  Calibrado según Decreto 1886/2015 (Art. 39, 40, 44)                       │
│  3 niveles: NORMAL (80%), PERTURBACIÓN (15%), INCIDENTE (5%)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Agentes Especializados

### 1. Orquestador (Puerto 8007) — ⭐ Central

**Responsabilidad:** Coordina todo el sistema. Es el punto de entrada del dashboard.

**Qué hace:**
- Recibe datos crudos del dashboard (`/orquestar` o `/orquestar_langgraph`)
- Consulta agentes especializados vía HTTP
- Correlaciona resultados de múltiples fuentes
- Integra LLM (Gemini) para razonamiento contextual
- Consulta RAG para normativa colombiana (Decreto 1886/2015)
- Broadcast de eventos al dashboard via WebSocket
- Mantiene historial de eventos en memoria

**Endpoints principales:**
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/orquestar` | POST | Flujo clásico — recibe datos crudos |
| `/orquestar_langgraph` | POST | Flujo LangGraph con memoria persistente |
| `/ws/eventos` | WebSocket | Broadcast en tiempo real al dashboard |
| `/rag/consultar` | POST | Consulta normativa con LLM |
| `/historial` | GET | Historial de eventos |
| `/health` | GET | Estado del sistema y agentes |

**Tecnología:** FastAPI + LangGraph + WebSocket

---

### 2. Agente Gases (Puerto 8001) — 🧪 Activo

**Responsabilidad:** Análisis completo de sensores de gases.

**Qué hace:**
1. **Clasificación por umbrales** — aplica Decreto 1886/2015 (Art. 39, 40, 44)
2. **Detección de anomalías** — Isolation Forest + detección deincrementos bruscos
3. **Predicción LSTM** — predice niveles de gases a 15, 30, 45, 60, 75, 90 minutos
4. **RAG** — consulta normativa según gases críticos y nivel de riesgo
5. **Genera acciones** — según el nivel de riesgo (desde monitoreo rutinario hasta evacuación)

**Modelos que usa:**
- `lstm_gases_{zona}.keras` — predicción de series temporales
- `isolation_forest.pkl` — detección de anomalías multivariadas
- `lstm_scalers_gases_nuevos.pkl` — normalización de datos

**Zonas monitoreadas:**
- `Frente_A_Sogamoso`
- `Frente_B_Mongua`
- `Galeria_Central`
- `Bocamina`

**Endpoints principales:**
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/analizar` | POST | Analiza lectura de gases |
| `/ciclo/{zona}` | POST | Ciclo autónomo (recolecta del simulador) |
| `/predictor/status` | GET | Diagnóstico del predictor LSTM |
| `/historial/{zona}` | GET | Historial de lecturas |

**Tecnología:** FastAPI + LSTM (NumPy inference) + Isolation Forest

---

### 3. Agente Geomecánico (Puerto 8003) — ⏳ No activo

**Responsabilidad:** Análisis de estabilidad geomecánica (deformación, vibración, presión).

**Estado:** Preparado pero no implementado en producción. Los modelos LSTM para geomecánica están pendientes.

---

### 4. Agente Imágenes (Puerto 8002) — ⏳ No activo

**Responsabilidad:** Análisis de imágenes de cámaras de seguridad.

**Estado:** Arquitectura preparada para modelos cGAN, pero no implementado en producción.

---

### 5. Simulador (Puerto 8005) — 🔄 Activo

**Responsabilidad:** Genera datos sintéticos de sensores para pruebas y demo.

**Qué hace:**
- Simula lecturas de gases (CH4, CO, CO2, O2, H2S)
- Simula temperatura y humedad
- three behavior levels:
  - **NORMAL (80%):** Operación rutinaria → SEGURO
  - **PERTURBACIÓN (15%):** Eventos operacionales → INFORMATIVO
  - **INCIDENTE (5%):** Fallos de seguridad → PRECAUCIÓN a EVACUACIÓN

**Calibración normativa:**
- Decreto 1886/2015 (Art. 39, 40, 44)
- CH4: 0-1% vol. (alarma 20% LEL, crítico 100% LEL)
- CO: 0-25 ppm (TWA)
- CO2: 0.03-0.5% (alarma 0.5%, crítico 3%)
- O2: 19.5-23.5% (alarma <19.5%)
- H2S: 0-1 ppm (TWA)

---

## Comunicación entre Componentes

### Flujo Principal (HTTP REST)

```
Dashboard ──POST /orquestar──▶ Orquestador ──HTTP──▶ Agente Gases
 │                    │
                                  │                    ▼
                                  │              LSTM + Isolation Forest
                                  │                    │
                                  ▼◀────────respuesta──┘
 LangGraph + LLM + RAG
                                  │
                                  ▼
                            WebSocket broadcast
                                  │
                                  ▼
                            Dashboard (real-time)
```

### Communication Manager (Circuit Breaker)

El Orquestador usa `CommunicationManager` para comunicarse con los agentes:

```
Orquestador ──CommunicationManager──▶ Agente Gases
                                     (Circuit Breaker)
 │
                                         ├── CLOSED: llamadas normales
                                         ├── OPEN: falla rápida (después de 3 fallos)
                                         └── HALF_OPEN: prueba recuperación
```

**Patrón Circuit Breaker:**
- **CLOSED:** Llamadas normales, reintentos automáticos
- **OPEN:** Después de 3 fallos consecutivos, falla rápido sin llamar al agente
- **HALF_OPEN:** Después de 30 segundos, prueba si el agente se recuperó

---

## Componentes de Support

### RAG Engine (Búsqueda Vectorial)

**Qué hace:** Consulta el corpus normativo colombiano (Decreto 1886/2015).

**Cómo funciona:**
1. Fragmenta documentos normativos en chunks
2. Genera embeddings con `sentence-transformers` (modelo `all-MiniLM-L6-v2`)
3. Almacena en índice FAISS para búsqueda similarity rápida
4. Recupera fragmentos relevantes según la consulta

**Tecnología:** LangChain + FAISS + sentence-transformers

---

### LLM Engine (Google Gemini)

**Qué hace:** Genera razonamiento contextual sobre eventos de seguridad.

**Cómo funciona:**
- Usa Google Gemini 1.7.0 (versión fija para evitar backtracking)
- Recibe: zona, nivel de riesgo, correlaciones, lecturas, normativa
- Retorna: diagnóstico, acciones recomendadas, pronóstico, referencia normativa
- **Fallback:** Si no hay API key, retorna plantilla predefinida en <1ms

**Tecnología:** google-genai==1.7.0

---

### LangGraph Flow (Orquestación Cíclica)

**Qué hace:** Flujo cíclico con memoria persistente para monitoreo continuo.

**Nodos del grafo:**
1. **Recibir datos** — recibe lecturas de sensores
2. **Analizar gases** — consulta Agente Gases
3. **Analizar geo** — consulta Agente Geomecánico (pendiente)
4. **Analizar imágenes** — consulta Agente Imágenes (pendiente)
5. **Correlacionar** — correlaciona resultados de todos los agentes
6. **Razonar con LLM** — genera diagnóstico contextual
7. **Consultar RAG** — recupera normativa aplicable
8. **Decidir acciones** — determina acciones globales
9. **Actualizar estado** — guarda en memoria persistente (SQLite)

**Memoria:** AsyncSqliteSaver (persiste en disco) o MemorySaver (en RAM)

---

## Modelo de Datos

### Niveles de Riesgo (Enum)

| Nivel | Orden | Significado |
|-------|-------|-------------|
| `SEGURO` | 0 | Condiciones normales |
| `INFORMATIVO` | 1 | Evento operacional menor |
| `PRECAUCIÓN` | 2 | Anomalía detectada, verificar |
| `RIESGO_ALTO` | 3 | Peligro inmediato, suspender actividades |
| `EMERGENCIA` | 4 | Emergencia, evacuar zona |
| `EVACUACIÓN` | 5 | Evacuación total inmediata |

### Estructura de Evento Global

```json
{
  "id_evento": "evt_20260106_143022",
  "timestamp": "2026-01-06T14:30:22",
  "zona": "Frente_A_Sogamoso",
  "nivel_global": "RIESGO_ALTO",
  "gases_criticos": [
    {"gas": "CH4", "valor": 1.5, "unidad": "%", "nivel": "RIESGO_ALTO"}
  ],
  "correlaciones": ["CH4 elevado + CO elevado"],
  "acciones_globales": ["SUSPENDER ACTIVIDADES", "Evacuar frente"],
  "diagnostico_llm": "Concentración de metano 3× sobre el umbral...",
  "pronostico_llm": "📈 Tendencia CRECIENTE — monitoreo intensivo...",
  "datos_gases": {"CH4": 1.5, "CO": 35, "CO2": 0.3, "O2": 20.1, "H2S": 0.5}
}
```

---

## Configuración de Red

| Servicio | Host | Puerto |
|----------|------|--------|
| Dashboard (React) | localhost | 3000 |
| Orquestador |127.0.0.1 | 8007 |
| Agente Gases | 127.0.0.1 | 8001 |
| Agente Imágenes | 127.0.0.1 | 8002 |
| Agente Geomecánico | 127.0.0.1 | 8003 |
| Agente Monitor | 127.0.0.1 | 8004 |
| Simulador | 127.0.0.1 | 8005 |

---

## Arranque del Sistema

```powershell
# Opción 1: Script completo (abre varias ventanas)
.\start_system.ps1

# Opción 2: Manual
# Ventana 1: Agente Gases
cd backend && python -m uvicorn agentes.gases.app:app --host 127.0.0.1 --port 8001

# Ventana 2: Simulador
cd backend && python -m uvicorn simulacion.app:app --host 127.0.0.1 --port 8005

# Ventana 3: Orquestador
cd backend && python -m uvicorn orquestador.app:app --host 127.0.0.1 --port 8007

# Ventana 4: Dashboard
cd frontend && pnpm run dev
```

---

*Agregar más detalles según avance del proyecto.*
