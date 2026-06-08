# 📚 Glosario de Conceptos — MINING_SAFETY_IA

> Archivo de estudio. Agregar conceptos importantes a medida que se avance.

---

## Modelos de Machine Learning en el Proyecto

### `.keras` — Archivos de modelo Keras (LSTM)

**¿Qué es?**
Archivo de modelo entrenado con Keras (TensorFlow/Keras). Un `.keras` es básicamente un ZIP que contiene:
- La arquitectura de la red neuronal (capas, activación, forma)
- Los pesos aprendidos durante el entrenamiento (en formato `.h5` dentro del ZIP)
- Configuración del optimizador y pérdida

**¿Para qué sirve en este proyecto?**
El sistema usa **inferencia NumPy pura** (sin TensorFlow en runtime). Esto significa:
1. Se leen los pesos `.h5` dentro del ZIP `.keras` usando `h5py`
2. Se ejecuta un forward-pass manual con NumPy (multiplicación de matrices)
3. No se necesita TensorFlow instalado para predecir — solo `h5py` y `numpy`

Cada zona tiene su propio modelo LSTM:
- `lstm_gases_Bocamina.keras`
- `lstm_gases_Frente_A_Sogamoso.keras`
- `lstm_gases_Frente_B_Mongua.keras`
- `lstm_gases_Galeria_Central.keras`

**¿Por qué es importante?**
Sin estos archivos, el predictor LSTM no puede hacer predicciones. El sistema hace fallback a modo vacío si no los encuentra.

---

### `.pkl` — Archivos Pickle (serialización Python)

**¿Qué es?**
Formato de serialización nativo de Python. Permite guardar objetos Python completos (modelos, datos, etc.) en un archivo binario.

**¿Para qué sirve en este proyecto?**

1. **`lstm_scalers_gases_nuevos.pkl`**
   - Contiene los **scalers** (Normalizer/StandardScaler) usados para normalizar los datos de entrada ANTES de entrenar
   - Sin estos scalers, las predicciones serían incorrectas porque las entradas no estarían en la misma escala que durante el entrenamiento
   - Es absolutamente esencial para que las predicciones tengan sentido

2. **`isolation_forest.pkl`**
   - Modelo **Isolation Forest** pre-entrenado para detección de anomalías
   - A diferencia del LSTM (que predice series temporales), Isolation Forest detecta **outliers** — puntos que se desvían del comportamiento normal
   - Es otro nivel de seguridad: si algo escapa al LSTM pero es muy anormal, Isolation Forest lo detecta

**¿Por qué es importante?**
- Los scalers son **irreemplazables** — sin ellos, las predicciones son ruido
- Isolation Forest es un modelo **complementario** al LSTM (no sustituto)

---

## Estructura de Modelos

```
modelos_reparados/gases/
├── lstm_gases_Bocamina.keras           # Modelo LSTM zona Bocamina
├── lstm_gases_Frente_A_Sogamoso.keras  # Modelo LSTM zona Frente A
├── lstm_gases_Frente_B_Mongua.keras    # Modelo LSTM zona Frente B
├── lstm_gases_Galeria_Central.keras    # Modelo LSTM zona Galería Central
├── isolation_forest.pkl                # Modelo Isolation Forest (anomalías)
└── lstm_scalers_gases_nuevos.pkl       # Scalers para todos los LSTM
```

> **Nota:** La carpeta se llama `modelos_reparados` por razones históricas. Es la carpeta activa de modelos.

---

## Conceptos Complementarios

### Inference vs Training
- **Training:** Proceso de ajustar los pesos de la red usando datos. Requiere TensorFlow y mucha potencia de cálculo.
- **Inference:** Proceso de usar los pesos ya ajustados para hacer predicciones. Este proyecto usa **inferencia NumPy pura**, lo que permite correr sin TensorFlow.

### Fallback mode
Cuando los modelos no se pueden cargar (archivo corrupto, faltante, etc.), el sistema no crashea — entra en **modo fallback** que devuelve predicciones vacías o valores por defecto. Esto es intencional para mantener el sistema corriendo aunque los modelos no estén disponibles.

---

## MLOps — Machine Learning Operations

### ¿Qué es?

MLOps es un conjunto de prácticas para **desplegar y mantener modelos ML en producción** de manera confiable. Combina DevOps, Machine Learning e Ingeniería de Datos.

### Componentes clave

| Componente | Descripción |
|------------|-------------|
| **CI/CD** | Integración y entrega continua de código y modelos |
| **Continuous Training (CT)** | Reentrenamiento automático de modelos cuando neuevos datos llegan |
| **Model Registry** | Versionado y tracking de modelos (qué versión está en producción, quién lo entrenó, métricas) |
| **Feature Store** | Repositorio centralizado de features (datos de entrada) para entrenamiento y producción |
| **Monitoring** | Monitoreo de performance del modelo en producción (drift, accuracy, latencia) |
| **Data Versioning** | Versionado de datos de entrenamiento (DVC, Pachyderm) |

### Elementos MLOps que este proyecto YA tiene

| Elemento | Estado | Detalle |
|----------|--------|---------|
| Modelos separados del código | ✅ | `modelos_reparados/gases/` vs código en `backend/` |
| Inference sin TF | ✅ | NumPy puro — buena práctica de producción |
| requirements separados | ✅ | `requirements.txt` (runtime) vs `requirements-train.txt` (entrenamiento) |
| Datos simulados | ✅ | El simulador genera datos sintéticos |

### Elementos MLOps que este proyecto NO tiene

| Elemento | Estado | Detalle |
|----------|--------|---------|
| **Model Registry** | ❌ | No hay versionado de modelos. Los `.keras` no tienen metadata |
| **Feature Store** | ❌ | No hay repositorio centralizado de features |
| **Continuous Training** | ❌ | No hay pipeline de reentrenamiento automático |
| **Monitoring** | ❌ | No hay tracking de performance del modelo en producción |
| **Data Versioning** | ❌ | `dataset_gases.csv` existe pero no está versionado ni es usado |
| **CI/CD para ML** | ❌ | No hay validación automática de modelos antes de desplegar |

### ¿Por qué no evolucionar a MLOps completo?

- Requiere infraestructura adicional (MLflow, feature store, monitoring tools)
- Entrenamiento automático necesita pipeline de datos continuo
- Tiempo y recursos para mantener más servicios
- Este proyecto es un **sistema de demostración/inferencia**, no una plataforma de ML productiva

### Enfoque actual del proyecto

El proyecto se enfoca en:
- **Sistema de inferencia** con datos simulados
- **Multiagente** para monitoreo y alertas
- **Dashboard** para visualización
- **Buena arquitectura** (agentes separados, configuración centralizada)

---

## Arquitectura del Sistema

Ver `ARCHITECTURE.md` para documentación completa de:
- Vista general del sistema
- Agentes especializados (Orquestador, Gases, Geomecánico, Imágenes, Simulador)
- Comunicación entre componentes (HTTP REST, WebSocket, Circuit Breaker)
- Componentes de soporte (RAG, LLM, LangGraph)
- Modelo de datos y niveles de riesgo
- Configuración de red y arranque

---

---

## Simulador de Gases — Niveles de Comportamiento

### ¿Qué es un "ciclo" del simulador?

El simulador genera nuevas lecturas de gases cada ~15 segundos (configurable). Cada generación de un conjunto nuevo de lecturas es un **ciclo**.

### Distribución probabilística

| Nivel | Probabilidad | Qué representa | Ejemplo |
|-------|-------------|-----------------|---------|
| **NORMAL (SEGURO)** | 80% | Operación rutinaria | CH4 bajo, CO normal, O2 OK |
| **PERTURBACIÓN (INFORMATIVO)** | 15% | Evento operacional esperado | Voladura, equipo diésel en marcha, ventilación reducida temporalmente |
| **INCIDENTE (PRECAUCIÓN a EVACUACIÓN)** | 5% | Fallo real de seguridad | Fuga de gas, sensor defectuoso, acumulación de metano |

### Ejemplo numérico

Si el sistema pasa **100 ciclos** del simulador:

```
80 ciclos → SEGURO      (condiciones normales)
15 ciclos → PERTURBACIÓN (eventos operacionales esperados)
 5 ciclos → INCIDENTE  (situaciones de riesgo real)
```

### ¿Por qué esta distribución?

Refleja la realidad de una mina subterránea:
- **~80%** → Condiciones normales con ventilación funcionando
- **~15%** → Eventos operacionales esperados (voladuras, mantenimiento)
- **~5%** → Situaciones de riesgo real (son estadísticamente raras también)

### Implementación técnica

La distribución se implementa con `random.choices()` con pesos en `simulador.py`:
```python
# Pseudocódigo
opciones = ["NORMAL", "PERTURBACION", "INCIDENTE"]
pesos = [0.80, 0.15, 0.05]
nivel = random.choices(opciones, weights=pesos)[0]
```

---

## LSTM — Long Short-Term Memory

### ¿Qué es?

LSTM (Long Short-Term Memory) es un tipo de **red neuronal recurrente (RNN)** diseñada para aprender patrones en **secuencias de datos** donde el orden temporal importa.

Fue introducida por Hochreiter y Schmidhuber en 1997~\cite{hochreiter1997}.

### ¿Por qué se llama "Long Short-Term Memory"?

Una RNN común tiene un problema: cuando la secuencia es larga, el gradiente (la señal de error) se **desvanece** al propagarse hacia atrás, haciendo que la red "olvide" información de los primeros pasos.

LSTM resuelve esto con un mecanismo llamado **compuerta de puerta (gate mechanism)**:

```
Celda LSTM:
┌─────────────────────────────────────────────┐
│  h_{t-1} ──►│ Gates │──► h_t            │
│             │ i, f, o  │                    │
│  x_t ──────►│ (input, │ │
│             │ forget, │                    │
│             │ output) │                    │
│             └──────────┘                    │
└─────────────────────────────────────────────┘

i = forget gate   → ¿cuánta info anterior descartar?
f = input gate     → ¿cuánta info nueva guardar?
o = output gate    → ¿cuánta info de la celda usar para la salida?
```

### ¿Cómo funciona en este proyecto?

**Entrada:** Las últimas 24 lecturas de gases (ventana de ~6 horas, una lectura cada 15 min)

**Proceso:**
1. La secuencia de24 lecturas entra a la primera capa LSTM (128 unidades)
2. La primera capa pasa su salida a la segunda capa LSTM (64 unidades)
3. La segunda capa produce un vector de 30 valores
4. Se reordena a (6, 5) → 6 pasos de predicción × 5 gases

**Salida:** Predicción de los próximos 6 pasos (90 minutos)

```
Entrada (24,5) → LSTM(128) → LSTM(64) → Dense(30) → Salida (6, 5)
                 24 pasos1 paso30 units6×5 gases
                  ←─── historia ────→    ←─── futuro ────→
```

### Detalle de cada bloque (arquitectura)

**BLOQUE 1 — ENTRADA**
- Forma: `(24, 5)`
- Significado: 24 lecturas históricas × 5 gases
- Contenido de cada lectura: `[CH₄, CO, O₂, CO₂, H₂S]`
- Representación: Cajita con "24 × 5" y flecha entrando

**BLOQUE 2 — CAPA LSTM 1**
- Unidades: 128
- `return_sequences=True`
- Entrada: `(24, 5)` → Salida: `(24, 128)` (24 pasos, 128 features)
- Significado: Produce un vector de 128 valores por cada paso temporal
- En Lucidchart: Rectángulo labeled "LSTM(128)"

**BLOQUE 3 — CAPA LSTM 2**
- Unidades: 64
- `return_sequences=False`
- Entrada: `(24, 128)` → Salida: `(64,)` (1 solo vector de 64 valores)
- Significado: Resume toda la secuencia en un único vector de estado
- En Lucidchart: Rectángulo labeled "LSTM(64)"

**BLOQUE 4 — DENSE**
- Neuronas: 30
- Entrada: `(64,)` → Salida: `(30,)`
- En Lucidchart: Rectángulo labeled "Dense(30)"

**BLOQUE 5 — SALIDA**
- Forma final: `(6, 5)` — reshape de los 30 valores
- Significado: 6 pasos de predicción × 5 gases
- Horizonte temporal: 90 minutos (6 × 15 min)
- En Lucidchart: Cajita labeled "(6, 5)"

### ¿Por qué LSTM y no otro modelo?

| Característica | LSTM | otros |
|----------------|------|-------|
| Secuencias largas | ✅ Memoria a largo plazo | RNN simple: olvida rápido |
| Dependencias temporales | ✅ Gate mechanism | ARIMA: solo lineal |
| Múltiples features | ✅ Multivariado | univariate |
| Entrenamiento | ✅ Backpropagation | — |

### NumPy puro en runtime

Lo interesante de este proyecto es que la **inferencia** LSTM se hace en **NumPy puro** — sin TensorFlow. Esto significa:
- No se necesita GPU
- No se necesita TensorFlow instalado
- Los pesos se leen directamente del archivo `.h5` dentro del `.keras`
- Solo se usa `h5py` + `numpy`

---

*Agregar más conceptos según avance del proyecto.*
