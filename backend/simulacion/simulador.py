"""
simulador.py — Simulador de sensores del entorno minero.
Genera datos sintéticos realistas y los envía automáticamente
al Agente de Gases y al Orquestador vía HTTP en tiempo real.

Modos de operación:
  - NORMAL:    Lecturas dentro de parámetros normales.
  - EVENTO:    Inyecta un evento de riesgo aleatorio.
  - CONTINUO:  Bucle infinito a intervalos configurables.
"""

from __future__ import annotations

import asyncio
import random
import time
from datetime import datetime
from typing import Optional

import httpx
import numpy as np

from backend.shared.config import settings
from backend.shared.logger import get_logger

log = get_logger("simulador")

random.seed(42)
np.random.seed(42)

# ── Parámetros base de gases por zona ─────────────────────────────────────────
PERFILES_ZONA = {
    "Frente_A_Sogamoso": {"CH4": (0.65, 0.18), "CO": (17, 5), "CO2": (0.21, 0.07),
                           "O2": (20.6, 0.22), "H2S": (0.55, 0.14)},
    "Frente_B_Mongua":   {"CH4": (0.50, 0.15), "CO": (15, 4), "CO2": (0.18, 0.06),
                           "O2": (20.7, 0.20), "H2S": (0.40, 0.12)},
    "Galeria_Central":   {"CH4": (0.45, 0.12), "CO": (13, 4), "CO2": (0.16, 0.05),
                           "O2": (20.8, 0.18), "H2S": (0.35, 0.10)},
    "Bocamina":          {"CH4": (0.30, 0.10), "CO": (10, 3), "CO2": (0.13, 0.04),
                           "O2": (20.9, 0.15), "H2S": (0.25, 0.08)},
}

PERFILES_GEO = {
    "Frente_A_Sogamoso": {"deformacion_mm": (1.8,0.6), "vibracion_mms": (5.0,1.5),
                           "presion_kpa": (42,8), "convergencia_mm": (2.5,0.8),
                           "indice_estabilidad": (0.82,0.05)},
    "Frente_B_Mongua":   {"deformacion_mm": (1.4,0.5), "vibracion_mms": (4.0,1.2),
                           "presion_kpa": (35,7), "convergencia_mm": (2.0,0.7),
                           "indice_estabilidad": (0.86,0.04)},
    "Galeria_Central":   {"deformacion_mm": (1.0,0.4), "vibracion_mms": (3.0,1.0),
                           "presion_kpa": (28,6), "convergencia_mm": (1.5,0.5),
                           "indice_estabilidad": (0.90,0.03)},
    "Bocamina":          {"deformacion_mm": (0.5,0.2), "vibracion_mms": (2.0,0.8),
                           "presion_kpa": (20,4), "convergencia_mm": (0.8,0.3),
                           "indice_estabilidad": (0.95,0.02)},
}

DETECCIONES_VISUALES = [
    ("normal",                0.82),
    ("polvo_excesivo",        0.06),
    ("persona_sin_casco",     0.04),
    ("persona_sin_chaleco",   0.03),
    ("humo",                  0.02),
    ("equipo_dañado",         0.02),
    ("persona_zona_restringida", 0.01),
]

EVENTOS_CRITICOS = [
    "escape_ch4",
    "incendio_galeria",
    "colapso_techo",
    "fuga_agua",
    "explosion_polvo",
]


class Simulador:
    """Generador de datos sintéticos y cliente HTTP para enviar al sistema."""

    def __init__(self) -> None:
        self._corriendo = False
        self._ciclo = 0
        self._client: Optional[httpx.AsyncClient] = None

    def _lectura_gas_normal(self, zona: str) -> dict:
        perfil = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
        return {
            gas: float(np.clip(np.random.normal(mu, sigma), 0, None))
            for gas, (mu, sigma) in perfil.items()
        }

    def _lectura_geo_normal(self, zona: str) -> dict:
        perfil = PERFILES_GEO.get(zona, PERFILES_GEO["Bocamina"])
        resultado = {}
        for var, (mu, sigma) in perfil.items():
            if var == "indice_estabilidad":
                resultado[var] = float(np.clip(np.random.normal(mu, sigma), 0.1, 1.0))
            else:
                resultado[var] = float(np.clip(np.random.normal(mu, sigma), 0, None))
        return resultado

    def _deteccion_visual(self) -> dict:
        dets, probs = zip(*DETECCIONES_VISUALES)
        deteccion = np.random.choice(dets, p=list(probs))
        return {
            "deteccion":  deteccion,
            "confianza":  round(float(np.random.uniform(0.75, 0.99)), 3),
            "n_personas": random.randint(0, 6),
        }

    def _inyectar_evento_critico(self, gases: dict, geo: dict) -> tuple[dict, dict, str]:
        """Modifica lecturas para simular un evento crítico."""
        tipo = random.choice(EVENTOS_CRITICOS)
        if tipo == "escape_ch4":
            gases["CH4"] = round(random.uniform(1.5, 5.5), 3)
            log.warning(f"[SIM] Evento: ESCAPE CH4 → {gases['CH4']}%")
        elif tipo == "incendio_galeria":
            gases["CO"]  = round(random.uniform(80, 280), 1)
            gases["CO2"] = round(random.uniform(1.2, 2.8), 2)
            log.warning(f"[SIM] Evento: INCENDIO → CO={gases['CO']}ppm")
        elif tipo == "colapso_techo":
            geo["deformacion_mm"]   = round(random.uniform(15, 25), 2)
            geo["indice_estabilidad"] = round(random.uniform(0.1, 0.3), 3)
            geo["vibracion_mms"]    = round(random.uniform(30, 60), 1)
            log.warning(f"[SIM] Evento: COLAPSO → deform={geo['deformacion_mm']}mm")
        elif tipo == "fuga_agua":
            gases["O2"] = round(random.uniform(17.0, 18.5), 2)
            log.warning(f"[SIM] Evento: FUGA AGUA → O2={gases['O2']}%")
        elif tipo == "explosion_polvo":
            gases["CH4"] = round(random.uniform(1.2, 3.0), 3)
            gases["CO"]  = round(random.uniform(60, 200), 1)
            log.warning(f"[SIM] Evento: EXPLOSIÓN POLVO → CH4={gases['CH4']}% CO={gases['CO']}ppm")
        return gases, geo, tipo

    async def _enviar_ciclo(self, zona: str, forzar_evento: bool = False) -> dict:
        """Genera datos y los envía al Orquestador."""
        gases  = self._lectura_gas_normal(zona)
        geo    = self._lectura_geo_normal(zona)
        imagen = self._deteccion_visual()
        tipo_evento = "normal"

        # Probabilidad de evento crítico: 5% por ciclo
        if forzar_evento or random.random() < 0.05:
            gases, geo, tipo_evento = self._inyectar_evento_critico(gases, geo)

        payload = {"zona": zona, "gases": gases, "imagen": imagen, "geo": geo}

        try:
            url = f"http://{settings.orquestador_host}:{settings.orquestador_port}/orquestar"
            resp = await self._client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            resultado = resp.json()
            nivel = resultado.get("nivel_global", "?")
            log.info(f"[SIM] Ciclo {self._ciclo} | {zona} | {tipo_evento} | Nivel: {nivel}")
            return resultado
        except Exception as e:
            log.error(f"[SIM] Error enviando ciclo: {e}")
            return {}

    async def ejecutar_ciclo_unico(
        self, zona: Optional[str] = None, forzar_evento: bool = False
    ) -> dict:
        """Ejecuta un único ciclo de simulación."""
        async with httpx.AsyncClient() as client:
            self._client = client
            z = zona or settings.simulacion_zona_default
            return await self._enviar_ciclo(z, forzar_evento)

    async def ejecutar_continuo(
        self, zonas: Optional[list[str]] = None, max_ciclos: int = -1
    ) -> None:
        """
        Bucle continuo de simulación. Rota entre zonas.
        max_ciclos=-1 → infinito.
        """
        zonas_activas = zonas or list(settings.zonas)
        self._corriendo = True
        self._ciclo = 0

        async with httpx.AsyncClient() as client:
            self._client = client
            while self._corriendo:
                zona = zonas_activas[self._ciclo % len(zonas_activas)]
                await self._enviar_ciclo(zona)
                self._ciclo += 1
                if max_ciclos > 0 and self._ciclo >= max_ciclos:
                    break
                await asyncio.sleep(settings.simulacion_interval_seg)

        log.info(f"[SIM] Simulación terminada. Ciclos ejecutados: {self._ciclo}")

    def detener(self) -> None:
        self._corriendo = False


# ── FastAPI del simulador (Puerto 8005) ───────────────────────────────────────
from fastapi import FastAPI

sim_app = FastAPI(title="Simulador Sensores Minería", version="2.0.0")
simulador = Simulador()


@sim_app.post("/simular")
async def simular_ciclo(zona: str = "Frente_A_Sogamoso", evento: bool = False):
    """Dispara un ciclo de simulación manual."""
    resultado = await simulador.ejecutar_ciclo_unico(zona, forzar_evento=evento)
    return {"zona": zona, "evento_forzado": evento, "resultado": resultado}


@sim_app.post("/iniciar")
async def iniciar_simulacion(max_ciclos: int = -1):
    """Inicia la simulación continua en background."""
    asyncio.create_task(simulador.ejecutar_continuo(max_ciclos=max_ciclos))
    return {"estado": "simulacion_iniciada", "max_ciclos": max_ciclos}


@sim_app.post("/detener")
async def detener_simulacion():
    simulador.detener()
    return {"estado": "simulacion_detenida"}