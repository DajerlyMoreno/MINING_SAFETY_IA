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

*Agregar más conceptos según avance del proyecto.*
