"""
monitor.py — Lógica del Agente Monitor.
Supervisa la ejecución de rondas de inspección, el cumplimiento de los
planes de ventilación y mantiene el gemelo digital de la mina con el
historial de incidentes y alertas por frente de explotación.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from backend.shared.enums import EstadoAgente, NivelRiesgo, NIVEL_ORDEN
from backend.shared.config import settings
from backend.shared.logger import get_logger

log = get_logger("agente_monitor")


class GemeloDigital:
    """
    Gemelo digital de la mina: mantiene el estado actual y el historial
    de incidentes por zona para visualización y auditoría.
    """

    def __init__(self) -> None:
        # Estado actual por zona
        self._estado_zonas: dict[str, dict] = {
            zona: {
                "nivel_actual":      "SEGURO",
                "ultimo_evento_id":  None,
                "ultimo_ts":         None,
                "total_alertas":     0,
                "total_evacuaciones": 0,
            }
            for zona in settings.zonas
        }
        # Historial de eventos por zona (máx 200 por zona)
        self._historial: dict[str, list[dict]] = defaultdict(list)
        # Estado de agentes monitoreados
        self._agentes: dict[str, str] = {
            ag.nombre: EstadoAgente.ACTIVO.value for ag in settings.get_agentes()
        }
        # Rondas de inspección pendientes y completadas
        self._rondas: list[dict] = []

    # ── Estado del gemelo ──────────────────────────────────────────────────────

    def registrar_evento(self, zona: str, nivel: str, evento_id: str) -> None:
        """Actualiza el gemelo con un nuevo evento del orquestador/LangGraph."""
        if zona not in self._estado_zonas:
            return
        z = self._estado_zonas[zona]
        z["nivel_actual"]     = nivel
        z["ultimo_evento_id"] = evento_id
        z["ultimo_ts"]        = datetime.utcnow().isoformat()
        if NIVEL_ORDEN.get(NivelRiesgo(nivel), 0) >= 4:
            z["total_evacuaciones"] += 1
        if NIVEL_ORDEN.get(NivelRiesgo(nivel), 0) >= 2:
            z["total_alertas"] += 1
        self._historial[zona].append({
            "ts":    z["ultimo_ts"],
            "nivel": nivel,
            "id":    evento_id,
        })
        if len(self._historial[zona]) > 200:
            self._historial[zona].pop(0)

    def estado_zona(self, zona: str) -> Optional[dict]:
        return self._estado_zonas.get(zona)

    def resumen_global(self) -> dict:
        nivel_max = max(
            (NIVEL_ORDEN.get(NivelRiesgo(z["nivel_actual"]), 0)
             for z in self._estado_zonas.values()),
            default=0,
        )
        return {
            "zonas":           self._estado_zonas,
            "nivel_global_max": nivel_max,
            "agentes":         self._agentes,
            "total_rondas":    len(self._rondas),
        }

    def historial_zona(self, zona: str, n: int = 20) -> list[dict]:
        return list(reversed(self._historial.get(zona, [])))[:n]

    # ── Rondas de inspección ───────────────────────────────────────────────────

    def registrar_ronda(self, zona: str, tipo: str, inspector: str) -> dict:
        ronda = {
            "id":        f"RONDA-{len(self._rondas)+1:04d}",
            "zona":      zona,
            "tipo":      tipo,
            "inspector": inspector,
            "ts_inicio": datetime.utcnow().isoformat(),
            "estado":    "EN_CURSO",
        }
        self._rondas.append(ronda)
        return ronda

    def completar_ronda(self, ronda_id: str, observaciones: str = "") -> Optional[dict]:
        for r in self._rondas:
            if r["id"] == ronda_id:
                r["estado"]        = "COMPLETADA"
                r["ts_fin"]        = datetime.utcnow().isoformat()
                r["observaciones"] = observaciones
                return r
        return None

    # ── Plan de ventilación ────────────────────────────────────────────────────

    def verificar_ventilacion(self, zona: str, caudal_m3s: float) -> dict:
        """
        Verifica cumplimiento del plan de ventilación.
        Decreto 1886/2015 Art. 74: mínimo 0.25 m³/s por trabajador,
        nunca inferior a 6 m³/s en el frente de avance.
        """
        cumple   = caudal_m3s >= 6.0
        deficite = max(0.0, 6.0 - caudal_m3s)
        return {
            "zona":       zona,
            "caudal_m3s": caudal_m3s,
            "cumple_art74": cumple,
            "deficit_m3s":  round(deficite, 2),
            "accion": (
                "Ventilación dentro de parámetros reglamentarios"
                if cumple else
                f"AUMENTAR caudal {deficite:.1f} m³/s (Art. 74 D.1886)"
            ),
        }

    # ── Estado de agentes ──────────────────────────────────────────────────────

    def actualizar_agente(self, nombre: str, estado: str) -> None:
        self._agentes[nombre] = estado

    def estados_agentes(self) -> dict[str, str]:
        return dict(self._agentes)


# Instancia global singleton
gemelo = GemeloDigital()
