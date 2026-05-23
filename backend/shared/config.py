"""
config.py — Configuración centralizada del sistema.
Lee variables de .env y expone objetos de configuración tipados.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

# ── Rutas base ────────────────────────────────────────────────────────────────
ROOT_DIR   = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = ROOT_DIR / "modelos"
RAG_DIR    = ROOT_DIR / "rag_data"
LOGS_DIR   = ROOT_DIR / "logs"
DATA_DIR   = ROOT_DIR / "datasets"

LOGS_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class AgentConfig:
    """Configuración de un agente especializado."""
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


@dataclass(frozen=True)
class ModelPaths:
    """Rutas absolutas a los modelos entrenados."""
    # Gases
    lstm_gases_dir:         Path = MODELS_DIR / "gases"
    isolation_forest_gases: Path = MODELS_DIR / "gases" / "isolation_forest_gases.pkl"
    # Geomecánico
    lstm_geo_dir:           Path = MODELS_DIR / "geomecanico"
    rf_geomecanico:         Path = MODELS_DIR / "geomecanico" / "rf_geomecanico.pkl"
    # RAG
    faiss_index_dir:        Path = RAG_DIR / "faiss_index"
    corpus_json:            Path = RAG_DIR / "corpus_normativo.json"

    def validate(self) -> list[str]:
        """Valida que los archivos críticos existan. Retorna lista de errores."""
        errores = []
        criticos = [
            self.isolation_forest_gases,
            self.rf_geomecanico,
            self.faiss_index_dir,
        ]
        for p in criticos:
            if not p.exists():
                errores.append(f"FALTA: {p}")
        return errores


@dataclass(frozen=True)
class SystemConfig:
    """Configuración global del sistema multiagente."""

    # ── Agentes especializados ──────────────────────────────────────────────
    agente_gases:      AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_GASES",      "127.0.0.1", 8001))
    agente_imagenes:   AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_IMAGENES",   "127.0.0.1", 8002))
    agente_geomecanico: AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_GEOMECANICO","127.0.0.1", 8003))
    agente_monitor:    AgentConfig = field(default_factory=lambda: AgentConfig(
        "AGENTE_MONITOR",    "127.0.0.1", 8004))
    simulador:         AgentConfig = field(default_factory=lambda: AgentConfig(
        "SIMULADOR",         "127.0.0.1", 8005))

    # ── Orquestador ───────────────────────────────────────────────────────────
    orquestador_host: str = "127.0.0.1"
    orquestador_port: int = 8000

    # ── RAG ──────────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    rag_k_resultados: int = 3

    # ── LSTM ──────────────────────────────────────────────────────────────────
    lstm_ventana:   int = 24  # pasos de historia
    lstm_horizonte: int = 6   # pasos de predicción
    lstm_min_por_paso: int = 15

    # ── Base de datos ─────────────────────────────────────────────────────────
    db_url: str = field(default_factory=lambda:
        os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{ROOT_DIR}/mineria_ia.db"))

    # ── Heartbeat ────────────────────────────────────────────────────────────
    heartbeat_interval_seg: int = 10
    heartbeat_timeout_seg:  int = 30

    # ── Simulación ────────────────────────────────────────────────────────────
    simulacion_interval_seg: float = 15.0
    simulacion_zona_default: str = "Frente_A_Sogamoso"

    # ── Zonas mineras ─────────────────────────────────────────────────────────
    zonas: tuple = (
        "Frente_A_Sogamoso",
        "Frente_B_Mongua",
        "Galeria_Central",
        "Bocamina",
    )

    # ── Rutas de modelos ──────────────────────────────────────────────────────
    model_paths: ModelPaths = field(default_factory=ModelPaths)

    def get_agentes(self) -> list[AgentConfig]:
        return [
            self.agente_gases, self.agente_imagenes,
            self.agente_geomecanico, self.agente_monitor,
        ]


# ── Instancia global ──────────────────────────────────────────────────────────
settings = SystemConfig()