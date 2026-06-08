# Sistema Multiagente de Monitoreo para Minería Subterránea 

Sistema de inteligencia artificial para monitoreo en tiempo real de condiciones de seguridad en minas subterráneas. Combina agentes especializados, modelos LSTM, detección de anomalías y un corpus normativo para detectar, predecir y notificar riesgos con referencia directa al Decreto 1886/2015 y estándares internacionales (OSHA, MSHA, NIOSH).

---

## Arquitectura

```
┌──────────────────────────────────────────────┐
│   Dashboard React + Vite  (puerto 3000)      │
│   • Gases en tiempo real + historial         │
│   • Predicciones LSTM (90 min)               │
│   • Mapa de riesgo por zona                  │
└───────────────────┬──────────────────────────┘
                    │ HTTP + WebSocket
┌───────────────────▼──────────────────────────┐
│   Orquestador  (puerto 8007)                 │
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
| Orquestador | 8007 | OK | Motor central de fusion multiagente |
| Agente de Gases | 8001 | OK | Analisis CH4, CO, CO2, O2, H2S |
| Agente de Imagenes | 8002 | Pendiente | Deteccion visual por camara |
| Agente Geomecanico | 8003 | Pendiente | Estabilidad estructural |
| Monitor de Personal | 8004 | Pendiente | Localizacion de trabajadores |
| Simulador | 8005 | OK | Generacion de datos de prueba |
| Dashboard | 3000 | OK | Interfaz React en tiempo real |

---

## Requisitos del sistema

- **Windows 10/11** (el sistema fue desarrollado y probado en Windows)
- **Python 3.11** (versiones 3.12+ pueden tener conflictos con TensorFlow 2.15)
- **Node.js 18+** con pnpm
- **Git** (opcional, para clonar el repositorio)

> **Importante:** El sistema funciona **SIN TensorFlow en runtime**. La inferencia LSTM usa NumPy puro. TensorFlow solo se necesita para **reentrenar modelos** (ver `requirements-train.txt`).

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

**Opcion B — Manual (runtime sin TensorFlow):**

```cmd
env\Scripts\activate
pip install -r requirements.txt
```

> **Nota:** `requirements.txt` NO incluye TensorFlow. El sistema usa inferencia NumPy pura. Si necesitas reentrenar modelos, usa `requirements-train.txt` con Python 3.11.

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
python -c "import h5py; import numpy as np; print('h5py:', h5py.__version__); print('numpy:', np.__version__)"
```

Debe mostrar:
```
h5py: 3.11.0
numpy: 1.26.4
```

> **Nota:** TensorFlow NO se verifica aquí porque no se instala en runtime. Si necesitas reentrenar modelos, instala `requirements-train.txt` y verifica con `python -c "import tensorflow as tf; print('TF:', tf.__version__)"`

---

## Dependencias criticas — runtime vs entrenamiento

El proyecto tiene **dos archivos de requirements** según el uso:

### Runtime (`requirements.txt`) — Producción
**NO incluye TensorFlow.** El sistema usa inferencia NumPy pura.

| Paquete | Version | Razon |
|---|---|---|
| `numpy` | 1.26.4 | Inferencia NumPy |
| `h5py` | 3.11.0 | Lectura de pesos .keras |
| `protobuf` | 4.25.3 | Dependencia de h5py |
| `ml-dtypes` | 0.5.0 | Versión pre-compilada (no requiere compilación) |

### Entrenamiento (`requirements-train.txt`) — Reentrenar modelos
**Solo para reentrenar modelos LSTM.** Requiere Python 3.11 EXCLUSIVAMENTE.

| Paquete | Version | Razon |
|---|---|---|
| `tensorflow` | 2.15.0 | Versión validada con los modelos |
| `tf-keras` | 2.15.0 | Keras 2 legacy (Keras 3 incompatible) |
| `numpy` | 1.26.4 | TF 2.15 no soporta NumPy 2.x |
| `ml-dtypes` | 0.2.0 | TF 2.15 requiere ~0.2.0 |

> **NO instalar** el paquete `keras` standalone en producción. Desde la versión 3.x es incompatible con TF 2.15 y rompe el entorno. Si ya está instalado: `pip uninstall keras -y`

---

## Solucion de problemas de instalacion

### Error: `No module named 'tensorflow'` (runtime)
Esto es **normal** en runtime. El sistema no usa TensorFlow. Verifica con:
```cmd
python -c "import h5py; import numpy as np; print('OK: h5py', h5py.__version__)"
```

### Error: `WinError 5 Acceso denegado`
El sistema esta corriendo y tiene archivos de Python bloqueados.
1. Ejecutar `stop_system.bat`
2. Verificar en el Administrador de Tareas que no haya procesos `python.exe`
3. Volver a intentar la instalacion

### Error: `ml-dtypes` no instala (necesita compilación)
Usa la versión pre-compilada:
```cmd
pip install ml-dtypes==0.5.0
```

### Error: `google-genai` backtracking
Versión fija para evitar conflictos:
```cmd
pip install google-genai==1.7.0
```

### Error: Puerto8000 en uso (Windows HTTP.SYS)
El Orquestador usa puerto **8007** (no 8000) para evitar el conflicto con Windows HTTP.SYS. Si necesitas cambiar: editar `backend/shared/config.py`.

---

## Ejecucion del sistema

### Iniciar todo el sistema

```cmd
start_system.bat
```

Esto abre ventanas separadas para cada componente:
- Orquestador (puerto 8007)
- Agente de Gases (puerto 8001)
- Agente Imagenes (puerto 8002) — pendiente
- Agente Geomecanico (puerto 8003) — pendiente
- Monitor (puerto 8004) — pendiente
- Simulador (puerto 8005)
- Dashboard React (puerto 3000)

### Usar el sistema

1. Abrir el navegador en `http://localhost:3000`
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

## Evaluacion experimental del sistema

El script `evaluacion_sistema.py` permite evaluar el rendimiento del sistema de forma automatizada sin necesidad del dashboard. Genera datos experimentales que se usan directamente en la seccion **Results and Discussion** del paper academico.

### Requisitos previos

1. El sistema debe estar corriendo con `start_system.bat`
2. El entorno virtual debe estar activado: `env\Scripts\activate`

### Ejecucion basica

```cmd
python evaluacion_sistema.py
```

Esto ejecutara **500 ciclos** por defecto y guardara los resultados en `evaluacion_resultados.csv`.

### Modificar la cantidad de ciclos

Editar la linea 28 del script:

```python
N_CICLOS = 500  # cambiar por el valor deseado
```

Ejemplo con 1000 ciclos:

```python
N_CICLOS = 1000
```

### Que hace el script

1. Espera a que los servicios (Orquestador puerto 8007, Agente Gases puerto 8001) esten disponibles
2. Ejecuta N ciclos alternando entre las 4 zonas mineras
3. Por cada ciclo captura:
   - Lectura real de gases (CH4, CO, CO2, O2, H2S)
   - Predicciones LSTM (6 pasos = 90 minutos)
   - Score y deteccion de Isolation Forest
   - Nivel de riesgo clasificado
4. Al finalizar imprime en consola:
   - MAE y RMSE por gas
   - Tasa de deteccion del Isolation Forest
   - Distribucion de niveles de riesgo
5. Guarda todos los datos crudos en `evaluacion_resultados.csv`

### Salida esperada en consola

```
=== Evaluacion del Sistema — 500 ciclos ===
Esperando servicios...
Servicios listos. Comenzando evaluacion...

  Progreso: 20/500 ciclos completados
  ...
  Progreso: 500/500 ciclos completados

CSV guardado en: C:\...\evaluacion_resultados.csv

==================================================
METRICAS DE EVALUACION
==================================================

Ciclos evaluados: 500
Alertas emitidas (EMERGENCIA/EVACUACION): 0 (0.0%)
Detecciones Isolation Forest: 368 (73.6%)

--- Error de Prediccion LSTM (MAE / RMSE) ---
  CH4: MAE=0.1248, RMSE=0.1787 (n=500)
  CO: MAE=4.2653, RMSE=6.1083 (n=500)
  CO2: MAE=0.0882, RMSE=0.1320 (n=500)
  O2: MAE=0.3148, RMSE=0.4014 (n=500)
  H2S: MAE=0.4703, RMSE=0.5173 (n=500)

--- Isolation Forest ---
  Score promedio: 0.6318
  Score maximo: 0.7035
  Score minimo: 0.5992
  Detecciones activas: 368/500 (73.6%)

--- Distribucion de Niveles ---
  PRECAUCION: 310 (62.0%)
  SEGURO: 190 (38.0%)
```

### Archivo de resultados

`evaluacion_resultados.csv` contiene una fila por ciclo con las columnas:

| Columna | Descripcion |
|---|---|
| `ciclo` | Numero del ciclo |
| `zona` | Zona minera evaluada |
| `timestamp` | Fecha y hora del ciclo |
| `nivel_clasificado` | SEGURO / PRECAUCION / RIESGO ALTO / EMERGENCIA / EVACUACION |
| `es_alerta` | True si el nivel es EMERGENCIA o EVACUACION |
| `if_score` | Score de anomalía del Isolation Forest |
| `if_detectado` | True si se detecto anomalia |
| `if_tipo` | Tipo: patron_multivariado / patron_incendio / incremento_brusco |
| `real_CH4`, `real_CO`, ... | Valores reales de cada gas |
| `pred_CH4_p1` a `pred_CH4_p6` | Predicciones LSTM (15 a 90 min) por gas |

### Generar graficos para el paper

Despues de ejecutar la evaluacion, se pueden generar los graficos en ingles con:

```cmd
python generar_graficos_results.py
```

Esto crea 3 imagenes PNG en `construccion-informe/images/`:

- `lstm_error_bar.png` — MAE y RMSE por gas
- `niveles_riesgo_pie.png` — Distribucion de niveles de riesgo
- `tipos_anomalia_bar.png` — Tipos de anomalias detectadas

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
│   │   ├── app.py          # Orquestador central (puerto 8007)
│   │   ├── communication_manager.py  # Circuit breaker
│   │   └── orquestador.py
│   ├── simulacion/
│   │   └── simulador.py    # Simulador experto (puerto 8005)
│   ├── rag/
│   │   └── rag_engine.py
│   ├── langgraph_flow/     # Flujo cíclico con memoria
│   │   ├── grafo.py
│   │   ├── nodos.py
│   │   └── estado.py
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
│       ├── lstm_scalers_gases_nuevos.pkl
│       └── isolation_forest.pkl
├── rag_data/
│   ├── corpus_normativo.json
│   └── faiss_index/
├── requirements.txt         # Runtime (sin TF)
├── requirements-train.txt   # Entrenamiento (con TF 2.15, Python 3.11)
├── instalar_dependencias.bat
├── start_system.bat
├── stop_system.bat
├── _start_dev.ps1          # Helper para desarrollo
├── ARCHITECTURE.md         # Documentación de arquitectura
└── CONCEPTOS_ML.md         # Glosario de conceptos ML
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
| `Frente_A_Sogamoso` | Alta actividad. CH4 y CO elevados. |
| `Frente_B_Mongua` | Frente activo secundario. |
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

### Orquestador `localhost:8007`

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

