# Sistema Multiagente de Monitoreo para Minería Subterránea 

Sistema de inteligencia artificial para monitoreo en tiempo real de condiciones de seguridad en minas subterráneas. Combina agentes especializados, modelos LSTM, detección de anomalías y un corpus normativo para detectar, predecir y notificar riesgos con referencia directa al Decreto 1886/2015 y estándares internacionales (OSHA, MSHA, NIOSH).

---

## Arquitectura

```
┌──────────────────────────────────────────────┐
│   Dashboard React + Vite  (puerto 5173)      │
│   • Gases en tiempo real + historial         │
│   • Predicciones LSTM (90 min)               │
│   • Mapa de riesgo por zona                  │
└───────────────────┬──────────────────────────┘
                    │ HTTP + WebSocket
┌───────────────────▼──────────────────────────┐
│   Orquestador  (puerto 8000)                 │
│   • Fusion de respuestas multiagente         │
│   • Reglas de correlacion entre senales      │
│   • Consulta RAG al corpus normativo         │
│   • Transmite eventos por WebSocket          │
└───────────────────┬──────────────────────────┘
                    │ HTTP con Circuit Breaker
        ┌───────────┼─────────────┐
        │           │             │
  ┌─────▼──┐  ┌─────▼──┐   ┌─────▼──┐
  │ Gases  │  │Imagenes│   │  Geo   │
  │ :8001  │  │ :8002  │   │ :8003  │
  │   OK   │  │ pend.  │   │ pend.  │
  └────────┘  └────────┘   └────────┘

┌──────────────────────────────────┐
│  Simulador  (puerto 8005)        │
│  • Genera datos sinteticos       │
│  • Inyecta eventos criticos (5%) │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│  Base de datos SQLite            │
│  mineria_ia.db (auto-generado)   │
│  • Historial de lecturas         │
│  • Eventos del orquestador       │
└──────────────────────────────────┘
```

### Componentes implementados

| Componente | Puerto | Estado | Descripcion |
|---|---|---|---|
| Orquestador | 8000 | OK | Motor central de fusion multiagente |
| Agente de Gases | 8001 | OK | Analisis CH4, CO, CO2, O2, H2S |
| Agente de Imagenes | 8002 | Pendiente | Deteccion visual por camara |
| Agente Geomecanico | 8003 | Pendiente | Estabilidad estructural |
| Monitor de Personal | 8004 | Pendiente | Localizacion de trabajadores |
| Simulador | 8005 | OK | Generacion de datos de prueba |
| Dashboard | 5173 | OK | Interfaz React en tiempo real |

---

## Requisitos del sistema

- **Windows 10/11** (el sistema fue desarrollado y probado en Windows)
- **Python 3.11** (versiones 3.12+ pueden tener conflictos con TF 2.15)
- **Node.js 18+** con npm
- **Git** (opcional, para clonar el repositorio)

> **Importante:** No usar Python 3.12+ ni versiones de TensorFlow distintas a 2.15.0. Ver sección de dependencias críticas.

---

## Instalacion paso a paso

### 1. Clonar o descomprimir el proyecto

Ubica la carpeta del proyecto. La estructura debe ser:

```
proyecto_mineria_ia/
├── backend/
├── frontend/
├── modelos_reparados/
├── rag_data/
├── requirements.txt
├── start_system.bat
├── stop_system.bat
└── instalar_dependencias.bat
```

### 2. Crear el entorno virtual de Python

Abre una terminal (cmd o PowerShell) dentro de la carpeta del proyecto:

```cmd
python -m venv env
```

### 3. Instalar dependencias del backend

**Opcion A — Script automatico (recomendado):**

Ejecuta `instalar_dependencias.bat` con doble clic. El script:
- Desinstala paquetes conflictivos automaticamente
- Instala las dependencias en el orden correcto
- Verifica que todo quedo bien al finalizar

**Opcion B — Manual:**

```cmd
env\Scripts\activate

:: Paso 1: fijar dependencias base de TF primero
pip install numpy==1.26.4 protobuf==4.25.3 ml-dtypes==0.2.0 h5py==3.11.0

:: Paso 2: instalar TensorFlow y tf-keras
pip install tensorflow==2.15.0 tf-keras==2.15.0

:: Paso 3: instalar el resto
pip install -r requirements.txt
```

### 4. Instalar dependencias del frontend

```cmd
cd frontend
pnpm install
cd ..
```

> Si no tienes pnpm instalado: `npm install -g pnpm`

### 5. Verificar la instalacion

```cmd
env\Scripts\activate
python -c "import tensorflow as tf; import tf_keras; import h5py; print('TF:', tf.__version__); print('tf_keras:', tf_keras.__version__); print('h5py:', h5py.__version__)"
```

Debe mostrar:
```
TF: 2.15.0
tf_keras: 2.15.0
h5py: 3.11.0
```

---

## Dependencias criticas — versiones exactas

El sistema usa TensorFlow 2.15.0. Las siguientes versiones son **obligatorias** para evitar conflictos:

| Paquete | Version | Razon |
|---|---|---|
| `tensorflow` | 2.15.0 | Version validada con los modelos |
| `tf-keras` | 2.15.0 | Keras 2 legacy requerido (Keras 3 es incompatible) |
| `numpy` | 1.26.4 | TF 2.15 no soporta NumPy 2.x |
| `protobuf` | 4.25.3 | TF 2.15 requiere < 5.0.0 |
| `ml-dtypes` | 0.2.0 | TF 2.15 requiere ~0.2.0 |
| `h5py` | 3.11.0 | Lectura de pesos de modelos .keras |

> **NO instalar** el paquete `keras` standalone. Desde la version 3.x es incompatible con TF 2.15 y rompe el entorno. Si ya esta instalado, ejecutar: `pip uninstall keras -y`

---

## Solucion de problemas de instalacion

### Error: `No module named 'tensorflow.compat'`
El paquete `keras` standalone (version 3.x) esta instalado y conflictua con TF 2.15.
```cmd
pip uninstall keras tensorflow-intel -y
pip install tensorflow==2.15.0 tf-keras==2.15.0
```

### Error: `WinError 5 Acceso denegado`
El sistema esta corriendo y tiene archivos de Python bloqueados.
1. Ejecutar `stop_system.bat`
2. Verificar en el Administrador de Tareas que no haya procesos `python.exe`
3. Volver a intentar la instalacion

### Error: `AttributeError: module 'tensorflow' has no attribute '__version__'`
Instalacion de TF corrupta. Reinstalar limpio:
```cmd
pip uninstall tensorflow tensorflow-intel keras tf-keras protobuf ml-dtypes -y
pip install numpy==1.26.4 protobuf==4.25.3 ml-dtypes==0.2.0
pip install tensorflow==2.15.0 tf-keras==2.15.0
```

### Error: `keras<2.16,>=2.15.0 required` al instalar
El paquete `tensorflow-intel` entra en conflicto. Desinstalarlo:
```cmd
pip uninstall tensorflow-intel -y
```

---

## Ejecucion del sistema

### Iniciar todo el sistema

```cmd
start_system.bat
```

Esto abre ventanas separadas para cada componente:
- Orquestador (puerto 8000)
- Agente de Gases (puerto 8001)
- Agente Imagenes (puerto 8002)
- Agente Geomecanico (puerto 8003)
- Monitor (puerto 8004)
- Simulador (puerto 8005)
- Dashboard React (puerto 5173)

### Usar el sistema

1. Abrir el navegador en `http://localhost:5173`
2. Pulsar **▶ Iniciar Simulacion**
3. Esperar ~2 minutos para que se acumule historial
4. Explorar las tres pestanas:
   - **Gases en Tiempo Real** — lecturas actuales + ultimas 10 por zona
   - **Predicciones LSTM** — horizonte de 90 minutos
   - **Mapa de Riesgo** — estado visual de cada zona

### Detener el sistema

```cmd
stop_system.bat
```

---

## Variables de entorno (`.env`)

Crear archivo `.env` en la raiz del proyecto (opcional, el sistema usa valores por defecto):

```env
DATABASE_URL=sqlite+aiosqlite:///./mineria_ia.db
EMBEDDING_MODEL=all-MiniLM-L6-v2
SIM_INTERVAL_SEG=15
SIM_ZONA_DEFAULT=Frente_A_Sogamoso
LOG_LEVEL=INFO
```

---

## Estructura de carpetas

```
proyecto_mineria_ia/
├── backend/
│   ├── agentes/
│   │   ├── gases/          # Agente de Gases (puerto 8001)
│   │   │   ├── app.py
│   │   │   ├── predictor.py    # Inferencia LSTM en NumPy puro
│   │   │   ├── umbrales.py
│   │   │   └── anomaly_detector.py
│   │   ├── imagenes/       # Pendiente
│   │   └── geomecanico/    # Pendiente
│   ├── orquestador/
│   │   └── app.py          # Orquestador central (puerto 8000)
│   ├── simulacion/
│   │   └── simulador.py    # Simulador experto (puerto 8005)
│   ├── rag/
│   │   └── rag_engine.py
│   └── shared/
│       ├── config.py
│       ├── database.py     # Persistencia SQLite
│       ├── enums.py
│       └── logger.py
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── GasPanel.jsx
│       │   ├── PrediccionesPanel.jsx
│       │   ├── RiskMap.jsx
│       │   └── AlertPanel.jsx
│       ├── hooks/
│       │   └── useWebSocket.js
│       └── App.jsx
├── modelos_reparados/
│   └── gases/
│       ├── lstm_gases_Frente_A_Sogamoso.keras
│       ├── lstm_gases_Frente_B_Mongua.keras
│       ├── lstm_gases_Galeria_Central.keras
│       ├── lstm_gases_Bocamina.keras
│       └── lstm_scalers_gases_nuevos.pkl
├── rag_data/
│   ├── corpus_normativo.json
│   └── faiss_index/
├── requirements.txt
├── instalar_dependencias.bat
├── start_system.bat
└── stop_system.bat
```

---

## Modelos de machine learning

### LSTM — Prediccion de series temporales

- **Entrada:** ultimas 24 lecturas (ventana de 6 horas a intervalos de 15 min)
- **Salida:** proximos 6 pasos (90 minutos de horizonte)
- **Gases:** CH4, CO, CO2, O2, H2S (5 variables)
- **Arquitectura:** LSTM(128) → Dropout → LSTM(64) → Dropout → Dense(30)
- **Guardado con:** Keras 3.13.2 (Google Colab)
- **Inferencia:** NumPy puro (sin keras en runtime, lee pesos directamente del H5)
- **Archivos:** `modelos_reparados/gases/lstm_gases_{zona}.keras`
- **Reentrenamiento:** notebook `ENTRENAR_LSTM_GASES.ipynb` en Google Colab

### IsolationForest — Deteccion de anomalias

- **Detecta:** patrones multivariados anomalos, fallas de sensor, incrementos bruscos
- **Archivo:** `modelos_reparados/gases/isolation_forest.pkl`
- **Fallback:** reglas heuristicas si el modelo no esta disponible

### RAG — Consulta normativa semantica

- **Corpus:** `rag_data/corpus_normativo.json` (Decreto 1886/2015 + estandares internacionales)
- **Indice vectorial:** `rag_data/faiss_index/` (reconstruido automaticamente si no existe)
- **Modelo de embeddings:** `all-MiniLM-L6-v2` (HuggingFace)

---

## Zonas monitoreadas

| Zona | Perfil de riesgo |
|---|---|
| `Frente_A` | Alta actividad. CH4 y CO elevados. |
| `Frente_B` | Frente activo secundario. |
| `Galeria_Central` | Zona de transito. Riesgo moderado. |
| `Bocamina` | Entrada principal. Riesgo bajo. |

---

## Normativa aplicada — Decreto 1886/2015

| Gas | Precaucion | Riesgo Alto | Emergencia | Evacuacion |
|---|---|---|---|---|
| CH4 (Metano) | >= 0.5% | — | >= 1.0% | >= 1.5% |
| CO (Monoxido) | >= 25 ppm | >= 50 ppm | >= 100 ppm | — |
| CO2 (Dioxido) | >= 0.5% | >= 1.0% | >= 1.5% | — |
| O2 (Oxigeno) | < 19.5% | — | < 17.0% | < 16.0% |
| H2S (Sulfuro) | >= 1 ppm | >= 10 ppm | >= 20 ppm | — |

---

## API — Endpoints principales

### Orquestador `localhost:8000`

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/orquestar` | Enviar lectura, recibir evento fusionado |
| `GET` | `/health` | Estado del orquestador y agentes |
| `GET` | `/estado` | Estadisticas (ciclos, evacuaciones) |
| `GET` | `/historial` | Historial de eventos |
| `WS` | `/ws/eventos` | Stream WebSocket en tiempo real |

### Agente de Gases `localhost:8001`

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/analizar` | Analizar lectura: CH4, CO, CO2, O2, H2S |
| `GET` | `/historial/{zona}` | Ultimas N lecturas de la zona |
| `GET` | `/predictor/status` | Diagnostico del predictor LSTM |
| `GET` | `/health` | Estado del agente |

### Simulador `localhost:8005`

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/iniciar` | Iniciar simulacion continua |
| `POST` | `/detener` | Detener simulacion |
| `POST` | `/simular` | Un ciclo manual |

---

## Niveles de riesgo

| Nivel | Color | Descripcion |
|---|---|---|
| SEGURO | Verde | Todos los parametros dentro de rangos normales |
| INFORMATIVO | Azul | Lectura registrada, sin accion requerida |
| PRECAUCION | Amarillo | Notificar jefe de turno, aumentar monitoreo |
| RIESGO ALTO | Naranja | Suspender actividades, evacuar frente |
| EMERGENCIA | Rojo | Evacuacion parcial, activar brigada de rescate |
| EVACUACION INMEDIATA | Purpura | Evacuacion total, llamar 123 y ANM |

---

## Referencias normativas

- **Decreto 1886 de 2015** — Reglamento de Seguridad en las Labores Mineras Subterraneas (Colombia)
- **OSHA 29 CFR 1910.146** — Permit-Required Confined Spaces
- **MSHA 30 CFR Part 57** — Safety and Health Standards — Underground Metal and Nonmetal Mines
- **NIOSH IDLH Values** — Immediately Dangerous to Life or Health
- **ACGIH TLV-TWA** — Threshold Limit Values for Chemical Substances

---

