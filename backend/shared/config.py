"""
config.py - Configuracion centralizada del sistema.
Lee variables de .env y expone objetos de configuracion tipados.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv opcional en dev

# Rutas base
ROOT_DIR   = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / "modelos"
RAG_DIR    = ROOT_DIR / "rag_data"
LOGS_DIR   = ROOT_DIR / "logs"
DATA_DIR   = ROOT_DIR / "datasets"

LOGS_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class AgentConfig:
    """Configuracion de un agente especializado."""
    nombre: str
    host:   str
    port:   int
    timeout_seg: float = 5.0
    reintentos:  int   = 3

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}/health"


MODELS_REPARADOS_DIR = ROOT_DIR / "modelos_reparados"


@dataclass(frozen=True)
class ModelPaths:
    """Rutas absolutas a los modelos entrenados.

    Estrategia de búsqueda LSTM:
      1. modelos_reparados/gases/  (versión con scalers corregidos)
      2. modelos/gases/            (versión original, fallback)
    """
    # Gases — usa modelos_reparados si existen, si no modelos/
    lstm_gases_dir:         Path = field(default_factory=lambda:
        MODELS_REPARADOS_DIR / "gases"
        if (MODELS_REPARADOS_DIR / "gases").exists()
        else MODELS_DIR / "gases")

    lstm_scalers_gases:     Path = field(default_factory=lambda:
        MODELS_REPARADOS_DIR / "gases" / "lstm_scalers_gases_nuevos.pkl"
        if (MODELS_REPARADOS_DIR / "gases" / "lstm_scalers_gases_nuevos.pkl").exists()
        else MODELS_DIR / "gases" / "lstm_scalers_gases_nuevos.pkl")

    isolation_forest_gases: Path = field(default_factory=lambda:
        MODELS_REPARADOS_DIR / "gases" / "isolation_forest.pkl"
        if (MODELS_REPARADOS_DIR / "gases" / "isolation_forest.pkl").exists()
        else MODELS_DIR / "gases" / "isolation_forest.pkl")

    # Geomecanico (no implementado aun)
    lstm_geo_dir:           Path = field(default_factory=lambda: MODELS_DIR / "geomecanico")
    rf_geomecanico:         Path = field(default_factory=lambda: MODELS_DIR / "geomecanico" / "rf_geomecanico.pkl")
    # RAG
    faiss_index_dir:        Path = field(default_factory=lambda: RAG_DIR / "faiss_index")
    corpus_json:            Path = field(default_factory=lambda: RAG_DIR / "corpus_normativo.json")

    def validate(self) -> list:
        """Valida archivos criticos. Retorna lista de advertencias."""
        advertencias = []
        if not self.isolation_forest_gases.exists():
            advertencias.append(f"FALTA: {self.isolation_forest_gases}")
        if not self.faiss_index_dir.exists():
            advertencias.append(f"FALTA: {self.faiss_index_dir}")
        if not self.lstm_gases_dir.exists():
            advertencias.append(f"FALTA directorio LSTM: {self.lstm_gases_dir}")
        return advertencias


@dataclass(frozen=True)
class SystemConfig:
    """Configuracion global del sistema multiagente."""

    # Agentes especializados
    agente_gases:       AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_GASES",       "127.0.0.1", 8001))
    agente_imagenes:    AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_IMAGENES",    "127.0.0.1", 8002))
    agente_geomecanico: AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_GEOMECANICO", "127.0.0.1", 8003))
    agente_monitor:     AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_MONITOR",     "127.0.0.1", 8004))
    simulador:          AgentConfig = field(default_factory=lambda: AgentConfig(
        "SIMULADOR",          "127.0.0.1", 8005))

    # Orquestador
    orquestador_host: str = "127.0.0.1"
    orquestador_port: int = 8000

    # RAG
    embedding_model:  str = "all-MiniLM-L6-v2"
    rag_k_resultados: int = 3

    # LSTM
    lstm_ventana:      int = 24
    lstm_horizonte:    int = 6
    lstm_min_por_paso: int = 15

    # Base de datos
    db_url: str = field(default_factory=lambda:
        os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{ROOT_DIR}/mineria_ia.db"))

    # Heartbeat
    heartbeat_interval_seg: int = 10
    heartbeat_timeout_seg:  int = 30

    # Simulacion
    simulacion_interval_seg: float = 15.0
    simulacion_zona_default: str   = "Frente_A_Sogamoso"

    # Zonas mineras
    zonas: tuple = (
        "Frente_A_Sogamoso",
        "Frente_B_Mongua",
        "Galeria_Central",
        "Bocamina",
    )

    # Rutas de modelos
    model_paths: ModelPaths = field(default_factory=ModelPaths)

    def get_agentes(self) -> list:
        return [
            self.agente_gases, self.agente_imagenes,
            self.agente_geomecanico, self.agente_monitor,
        ]


# Instancia global
settings = SystemConfig()
