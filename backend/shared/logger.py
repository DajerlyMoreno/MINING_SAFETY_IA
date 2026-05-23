"""
logger.py — Logger estructurado y centralizado.
Genera logs en formato JSON para facilitar análisis y monitoreo.
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from backend.shared.config import LOGS_DIR


class JSONFormatter(logging.Formatter):
    """Formateador que emite logs como JSON estructurado."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level":     record.levelname,
            "module":    record.name,
            "message":   record.getMessage(),
        }
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_dict.update(record.extra)
        return json.dumps(log_dict, ensure_ascii=False)


def get_logger(nombre: str) -> logging.Logger:
    """
    Crea o recupera un logger configurado para el módulo dado.

    Args:
        nombre: Nombre del módulo (ej: 'agente_gases', 'orquestador').

    Returns:
        Logger configurado con handler de archivo y consola.
    """
    logger = logging.getLogger(nombre)
    if logger.handlers:                    # evitar duplicar handlers
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = JSONFormatter()

    # Handler de consola (INFO+)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Handler de archivo (DEBUG+)
    log_file = LOGS_DIR / f"{nombre}.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger