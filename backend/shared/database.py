"""
database.py — Capa de persistencia SQLite para el sistema multiagente.
Guarda lecturas de gases por zona y permite recuperarlas al reiniciar.

Usa aiosqlite para operaciones no bloqueantes compatibles con FastAPI async.
La base de datos se crea automáticamente en ROOT_DIR/mineria_ia.db
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.shared.config import ROOT_DIR
from backend.shared.logger import get_logger

log = get_logger("database")

DB_PATH = ROOT_DIR / "mineria_ia.db"

# ── Esquema ────────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS lecturas_gases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zona        TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    CH4         REAL    NOT NULL DEFAULT 0,
    CO          REAL    NOT NULL DEFAULT 0,
    CO2         REAL    NOT NULL DEFAULT 0,
    O2          REAL    NOT NULL DEFAULT 20.9,
    H2S         REAL    NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lecturas_zona_ts
    ON lecturas_gases (zona, timestamp DESC);

CREATE TABLE IF NOT EXISTS eventos_orquestador (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_evento       TEXT    NOT NULL,
    zona            TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    nivel_global    TEXT    NOT NULL,
    explicacion     TEXT,
    acciones        TEXT,   -- JSON array
    normativa       TEXT    -- JSON array
);
"""


def _get_conn() -> sqlite3.Connection:
    """Conexión síncrona (para init y migraciones)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db() -> None:
    """Crea las tablas si no existen. Llamar una vez al arrancar."""
    try:
        conn = _get_conn()
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        log.info(f"Base de datos inicializada: {DB_PATH}")
    except Exception as e:
        log.error(f"Error inicializando base de datos: {e}")
        raise


# ── Operaciones síncronas simples (sin aiosqlite) ─────────────────────────────
# Usamos sqlite3 estándar con run_in_executor para no bloquear el event loop.

def _guardar_lectura_sync(zona: str, gases: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO lecturas_gases (zona, timestamp, CH4, CO, CO2, O2, H2S)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                zona,
                datetime.utcnow().isoformat(),
                gases.get("CH4", 0),
                gases.get("CO",  0),
                gases.get("CO2", 0),
                gases.get("O2",  20.9),
                gases.get("H2S", 0),
            )
        )
        conn.commit()
    finally:
        conn.close()


def _cargar_historial_sync(zona: str, n: int = 500) -> list[dict]:
    """Devuelve las últimas n lecturas de una zona, ordenadas de más antigua a más nueva."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT CH4, CO, CO2, O2, H2S
               FROM (
                   SELECT CH4, CO, CO2, O2, H2S, timestamp
                   FROM lecturas_gases
                   WHERE zona = ?
                   ORDER BY timestamp DESC
                   LIMIT ?
               ) sub
               ORDER BY timestamp ASC""",
            (zona, n)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _guardar_evento_sync(evento: dict) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO eventos_orquestador
               (id_evento, zona, timestamp, nivel_global, explicacion, acciones, normativa)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                evento.get("id_evento", ""),
                evento.get("zona", ""),
                evento.get("timestamp", datetime.utcnow().isoformat()),
                evento.get("nivel_global", "SEGURO"),
                evento.get("explicacion", ""),
                json.dumps(evento.get("acciones_globales", []), ensure_ascii=False),
                json.dumps(evento.get("normativa", []), ensure_ascii=False),
            )
        )
        conn.commit()
    finally:
        conn.close()


def _contar_lecturas_sync(zona: str) -> int:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT COUNT(*) as n FROM lecturas_gases WHERE zona = ?", (zona,)
        ).fetchone()
        return row["n"] if row else 0
    finally:
        conn.close()


# ── API async (wrapping síncrono con executor) ────────────────────────────────
import asyncio
from functools import partial


async def guardar_lectura(zona: str, gases: dict) -> None:
    """Guarda una lectura de gases en SQLite de forma no bloqueante."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, partial(_guardar_lectura_sync, zona, gases))
    except Exception as e:
        log.warning(f"Error guardando lectura en DB ({zona}): {e}")


async def cargar_historial(zona: str, n: int = 500) -> list[dict]:
    """Carga las últimas n lecturas de una zona desde SQLite."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_cargar_historial_sync, zona, n))
    except Exception as e:
        log.warning(f"Error cargando historial desde DB ({zona}): {e}")
        return []


async def guardar_evento(evento: dict) -> None:
    """Guarda un evento del orquestador en SQLite."""
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, partial(_guardar_evento_sync, evento))
    except Exception as e:
        log.warning(f"Error guardando evento en DB: {e}")


async def contar_lecturas(zona: str) -> int:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, partial(_contar_lecturas_sync, zona))
    except Exception:
        return 0
