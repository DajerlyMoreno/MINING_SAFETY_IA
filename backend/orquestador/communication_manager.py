"""
communication_manager.py — Gestión de comunicación HTTP entre el Orquestador
y los agentes especializados. Implementa circuit breaker y reintentos.
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional, Any

import httpx

from backend.shared.config import settings, AgentConfig
from backend.shared.enums import EstadoAgente, TipoAgente
from backend.shared.exceptions import AgenteNoDisponible
from backend.shared.logger import get_logger

log = get_logger("communication_manager")


class CircuitBreaker:
    """
    Patrón Circuit Breaker para proteger llamadas a agentes.
    CLOSED → llamadas normales.
    OPEN   → falla rápida sin llamar al agente (después de N fallos).
    HALF_OPEN → prueba si el agente se recuperó.
    """
    UMBRAL_FALLOS = 3
    TIEMPO_RESET_SEG = 30

    def __init__(self, nombre: str) -> None:
        self.nombre       = nombre
        self._fallos      = 0
        self._estado      = "CLOSED"
        self._ultimo_fallo: Optional[float] = None

    @property
    def abierto(self) -> bool:
        if self._estado == "OPEN":
            if time.time() - (self._ultimo_fallo or 0) > self.TIEMPO_RESET_SEG:
                self._estado = "HALF_OPEN"
                log.info(f"CircuitBreaker {self.nombre}: HALF_OPEN (probando recuperación)")
                return False
            return True
        return False

    def registrar_exito(self) -> None:
        self._fallos = 0
        self._estado = "CLOSED"

    def registrar_fallo(self) -> None:
        self._fallos += 1
        self._ultimo_fallo = time.time()
        if self._fallos >= self.UMBRAL_FALLOS:
            self._estado = "OPEN"
            log.warning(f"CircuitBreaker {self.nombre}: ABIERTO ({self._fallos} fallos)")


class CommunicationManager:
    """
    Gestiona todas las comunicaciones HTTP del Orquestador con los agentes.
    Provee métodos tipados para cada agente y maneja errores de red.
    """

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            ag.nombre: CircuitBreaker(ag.nombre)
            for ag in settings.get_agentes()
        }
        self._estados: dict[str, EstadoAgente] = {
            ag.nombre: EstadoAgente.ACTIVO
            for ag in settings.get_agentes()
        }
        self._latencias: dict[str, list[float]] = {
            ag.nombre: [] for ag in settings.get_agentes()
        }

    async def __aenter__(self) -> "CommunicationManager":
        self._client = httpx.AsyncClient(timeout=10.0)
        return self

    async def __aexit__(self, *args) -> None:
        if self._client:
            await self._client.aclose()

    async def _post(
        self, config: AgentConfig, endpoint: str, payload: dict
    ) -> Optional[dict]:
        """Llamada HTTP POST con circuit breaker, reintento y logging."""
        cb = self._circuit_breakers[config.nombre]
        if cb.abierto:
            log.warning(f"{config.nombre}: Circuit breaker ABIERTO — saltando llamada")
            self._estados[config.nombre] = EstadoAgente.OFFLINE
            return None

        url = f"{config.base_url}{endpoint}"
        for intento in range(config.reintentos):
            try:
                t0 = time.time()
                resp = await self._client.post(url, json=payload)
                resp.raise_for_status()
                lat = (time.time() - t0) * 1000
                self._latencias[config.nombre].append(lat)
                cb.registrar_exito()
                self._estados[config.nombre] = EstadoAgente.ACTIVO
                return resp.json()
            except httpx.TimeoutException:
                log.warning(f"{config.nombre}: timeout (intento {intento+1})")
            except httpx.HTTPStatusError as e:
                log.error(f"{config.nombre}: HTTP {e.response.status_code}")
                break
            except Exception as e:
                log.error(f"{config.nombre}: error inesperado: {e}")

        cb.registrar_fallo()
        self._estados[config.nombre] = EstadoAgente.DEGRADADO
        return None

    async def _get(self, config: AgentConfig, endpoint: str) -> Optional[dict]:
        """Llamada HTTP GET con manejo de errores."""
        url = f"{config.base_url}{endpoint}"
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.warning(f"GET {url} falló: {e}")
            return None

    # ── Llamadas tipadas por agente ───────────────────────────────────────────

    async def analizar_gases(self, zona: str, lectura: dict) -> Optional[dict]:
        payload = {"zona": zona, **lectura}
        return await self._post(settings.agente_gases, "/analizar", payload)

    async def analizar_imagen(
        self, zona: str, deteccion: str, confianza: float, n_personas: int
    ) -> Optional[dict]:
        payload = {
            "zona": zona, "deteccion": deteccion,
            "confianza": confianza, "n_personas": n_personas,
        }
        return await self._post(settings.agente_imagenes, "/analizar", payload)

    async def analizar_geo(self, zona: str, lectura: dict) -> Optional[dict]:
        payload = {"zona": zona, **lectura}
        return await self._post(settings.agente_geomecanico, "/analizar", payload)

    async def verificar_salud_agentes(self) -> dict[str, dict]:
        """Consulta /health de todos los agentes en paralelo."""
        tareas = {
            ag.nombre: self._get(ag, "/health")
            for ag in settings.get_agentes()
        }
        resultados = await asyncio.gather(*tareas.values(), return_exceptions=True)
        return dict(zip(tareas.keys(), resultados))

    def obtener_estados(self) -> dict[str, str]:
        return {k: v.value for k, v in self._estados.items()}

    def obtener_latencias_promedio(self) -> dict[str, float]:
        import statistics
        return {
            k: round(statistics.mean(v), 1) if v else 0.0
            for k, v in self._latencias.items()
        }