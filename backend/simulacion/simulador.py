"""
simulador.py — Simulador de sensores del entorno minero.
Calibrado según Decreto 1886/2015 (Colombia) y condiciones típicas de
minas de carbón subterráneas en Boyacá (cuencas Sogamoso-Mongua).

Tres niveles de comportamiento:
  1. NORMAL   (~80 %)  → SEGURO       — operación rutinaria
  2. PERTURBACIÓN (~15%) → INFORMATIVO — eventos operacionales esperados
     (voladuras, ventilación insuficiente, equipos diésel en marcha)
  3. INCIDENTE  (~5 %)  → PRECAUCIÓN a EVACUACIÓN — fallo real de seguridad

Referencia técnica:
  - Decreto 1886/2015 Arts. 64-69 (límites permisibles de gases)
  - Resolución 90708/2013 (Reglamento Técnico de Instalaciones Eléctricas)
  - NIOSH Handbook of Mining Hazards — seam gas liberation rates
  - Coals of the Boyacá Eastern Cordillera (SGC, 2018)
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

# ── Semilla para reproducibilidad ─────────────────────────────────────────────
random.seed(42)
np.random.seed(42)

# ═══════════════════════════════════════════════════════════════════════════════
# PERFILES NORMALES — línea base por zona
# Representan condiciones operativas estables con ventilación funcionando.
# Con estas distribuciones, ~98% de lecturas quedan en SEGURO
# (umbrales Decreto 1886: CH4<0.5%, CO<10ppm, CO2<0.5%, O2>19.5%, H2S<1ppm)
#
# Nota geológica: los Frentes tienen mayor liberación de CH4 que las galerías
# por exposición directa al manto carbonífero. El CO aumenta con actividad diésel.
# ═══════════════════════════════════════════════════════════════════════════════
PERFILES_ZONA = {
    # Frente A — zona más activa, manto con mayor índice de gasificación
    "Frente_A_Sogamoso": {
        "CH4": (0.28, 0.07),   # ppm seepage del manto; ventilación en 0.5 m/s
        "CO":  (5.8,  1.6),    # equipo diésel en operación (~4 máquinas)
        "CO2": (0.11, 0.03),   # respiración + oxidación lenta del carbón
        "O2":  (20.62, 0.10),  # ligeramente disminuido por consumo biológico/mecánico
        "H2S": (0.18, 0.07),   # piritas en el manto; bajo pero presente
    },
    # Frente B — activo pero manto menos gaseoso que Sogamoso
    "Frente_B_Mongua": {
        "CH4": (0.20, 0.06),
        "CO":  (4.5,  1.4),
        "CO2": (0.09, 0.02),
        "O2":  (20.68, 0.09),
        "H2S": (0.12, 0.06),
    },
    # Galería Central — vía de ventilación principal, gases diluidos en tránsito
    "Galeria_Central": {
        "CH4": (0.10, 0.04),
        "CO":  (3.2,  1.1),
        "CO2": (0.07, 0.02),
        "O2":  (20.75, 0.08),
        "H2S": (0.08, 0.04),
    },
    # Bocamina — entrada/salida; prácticamente condiciones atmosféricas externas
    "Bocamina": {
        "CH4": (0.03, 0.02),
        "CO":  (1.8,  0.7),
        "CO2": (0.05, 0.01),
        "O2":  (20.85, 0.06),
        "H2S": (0.04, 0.02),
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# PERTURBACIONES OPERACIONALES — generan INFORMATIVO transitorio (1-8 ciclos)
# Son eventos normales en minería; no constituyen emergencia, pero requieren
# seguimiento. El nivel vuelve a SEGURO cuando la perturbación termina.
# ═══════════════════════════════════════════════════════════════════════════════
PERTURBACIONES = {
    # Después de una voladura: nube de CO/CO2 antes de que la ventilación disperse
    "post_voladura": {
        "descripcion": "Fumes post-voladura — ventilación disipando CO",
        "gases": {"CO": (18, 35), "CO2": (0.25, 0.55)},   # rango [min, max]
        "duracion_ciclos": (3, 8),
        "prob": 0.06,   # 6% de probabilidad por ciclo
    },
    # Falla parcial de ventilador: CH4 sube lentamente hasta que se corrige
    "ventilacion_reducida": {
        "descripcion": "Ventilación insuficiente — acumulación gradual de CH4",
        "gases": {"CH4": (0.52, 0.90)},
        "duracion_ciclos": (4, 10),
        "prob": 0.05,
    },
    # Equipo diésel pesado en uso intensivo (pala cargadora, dumper)
    "diesel_intensivo": {
        "descripcion": "Equipo diésel en operación intensiva — CO elevado",
        "gases": {"CO": (12, 22), "CO2": (0.18, 0.35)},
        "duracion_ciclos": (2, 6),
        "prob": 0.04,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# INCIDENTES CRÍTICOS — generan PRECAUCIÓN → EVACUACIÓN (Art. 64-69 D.1886)
# Probabilidad: ~5% del total de ciclos
# ═══════════════════════════════════════════════════════════════════════════════
INCIDENTES = [
    {
        "tipo": "escape_ch4",
        "descripcion": "Escape súbito de CH4 desde fractura del manto",
        "gases":  {"CH4": (1.6, 4.5)},
        "nivel_esperado": "RIESGO ALTO",
    },
    {
        "tipo": "inicio_incendio",
        "descripcion": "Inicio de incendio — carbón espontáneo o cortocircuito",
        "gases":  {"CO": (55, 180), "CO2": (0.8, 2.2)},
        "nivel_esperado": "EMERGENCIA",
    },
    {
        "tipo": "deficiencia_oxigeno",
        "descripcion": "Deficiencia de O2 — desplazamiento por gases inertes",
        "gases":  {"O2": (16.5, 18.8)},
        "nivel_esperado": "RIESGO ALTO",
    },
    {
        "tipo": "explosion_polvo_carbon",
        "descripcion": "Explosión de polvo de carbón — presión + gases de combustión",
        "gases":  {"CH4": (1.5, 3.0), "CO": (70, 220)},
        "nivel_esperado": "EVACUACIÓN INMEDIATA",
    },
    {
        "tipo": "fuga_h2s",
        "descripcion": "Fuga de H2S desde agua de mina o yacimiento",
        "gases":  {"H2S": (12, 45)},
        "nivel_esperado": "RIESGO ALTO",
    },
    {
        "tipo": "escape_ch4_masivo",
        "descripcion": "Escape masivo de CH4 — zona de alta presión",
        "gases":  {"CH4": (3.5, 6.0), "O2": (18.5, 19.2)},
        "nivel_esperado": "EVACUACIÓN INMEDIATA",
    },
]

# Peso relativo de cada incidente (los menos severos son más frecuentes)
PESOS_INCIDENTES = [0.30, 0.25, 0.20, 0.10, 0.10, 0.05]

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
    ("normal",                   0.80),
    ("polvo_excesivo",           0.06),
    ("persona_sin_casco",        0.04),
    ("persona_sin_chaleco",      0.03),
    ("humo",                     0.03),
    ("equipo_dañado",            0.02),
    ("persona_zona_restringida", 0.02),
]


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULADOR
# ═══════════════════════════════════════════════════════════════════════════════
class Simulador:
    """Generador de datos sintéticos y cliente HTTP para enviar al sistema."""

    # Factor de inercia temporal (0 = sin memoria, 1 = sin cambio).
    # 0.72 → cada lectura es 72% del valor anterior + 28% del objetivo.
    # Produce autocorrelación natural y evita saltos bruscos entre ciclos normales.
    _ALPHA = 0.72

    def __init__(self) -> None:
        self._corriendo = False
        self._ciclo     = 0
        self._client: Optional[httpx.AsyncClient] = None
        # Estado de perturbación activa por zona: {zona: {gas: valor, ciclos_restantes}}
        self._perturbacion_activa: dict = {}
        # Último valor medido por zona y gas (para suavizado temporal)
        self._estado_actual: dict = {}

    def _init_estado(self, zona: str) -> None:
        """Inicializa el estado de una zona con la línea base del perfil."""
        if zona not in self._estado_actual:
            perfil = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
            self._estado_actual[zona] = {
                gas: float(np.random.normal(mu, sigma * 0.5))
                for gas, (mu, sigma) in perfil.items()
            }

    # ── Lectura normal con inercia temporal ────────────────────────────────────
    def _lectura_gas_normal(self, zona: str) -> dict:
        """
        Genera una lectura con continuidad temporal (proceso AR(1)):
          nuevo = alpha * anterior + (1-alpha) * objetivo + ruido_pequeño
        El resultado evoluciona suavemente en lugar de saltar de forma aleatoria.
        """
        self._init_estado(zona)
        perfil  = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
        previo  = self._estado_actual[zona]
        alpha   = self._ALPHA
        gases   = {}

        for gas, (mu, sigma) in perfil.items():
            # Objetivo: valor de la línea base con pequeño ruido
            objetivo = float(np.random.normal(mu, sigma * 0.4))
            # Inercia: mezcla entre el valor anterior y el objetivo
            nuevo = alpha * previo[gas] + (1 - alpha) * objetivo
            # Ruido de sensor (muy pequeño, simula resolución del sensor)
            nuevo += float(np.random.normal(0, sigma * 0.06))
            if gas == "O2":
                nuevo = float(np.clip(nuevo, 18.0, 21.0))
            else:
                nuevo = float(np.clip(nuevo, 0.0, None))
            gases[gas] = round(nuevo, 4)

        # Guardar como nuevo estado
        self._estado_actual[zona] = dict(gases)
        return gases

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

    # ── Perturbaciones operacionales (INFORMATIVO transitorio) ─────────────────
    def _aplicar_perturbacion(self, gases: dict, zona: str) -> tuple[dict, str]:
        """
        Gestiona perturbaciones operacionales.
        Si hay una activa para esta zona, continúa aplicándola.
        Si no, evalúa si inicia una nueva.
        Retorna (gases_modificados, descripcion).
        """
        estado = self._perturbacion_activa.get(zona)

        # Continuar perturbación en curso
        if estado and estado["ciclos_restantes"] > 0:
            for gas, valor in estado["gases_override"].items():
                gases[gas] = round(valor * random.uniform(0.88, 1.12), 4)
            estado["ciclos_restantes"] -= 1
            if estado["ciclos_restantes"] == 0:
                del self._perturbacion_activa[zona]
                log.info(f"[SIM] {zona}: perturbación '{estado['tipo']}' finalizada")
            return gases, estado["tipo"]

        # Evaluar inicio de nueva perturbación
        for tipo, config in PERTURBACIONES.items():
            if random.random() < config["prob"]:
                duracion = random.randint(*config["duracion_ciclos"])
                # Valor medio del rango para la perturbación
                gases_override = {
                    gas: random.uniform(lo, hi)
                    for gas, (lo, hi) in config["gases"].items()
                }
                self._perturbacion_activa[zona] = {
                    "tipo":            tipo,
                    "gases_override":  gases_override,
                    "ciclos_restantes": duracion - 1,
                }
                # Aplicar primera lectura
                for gas, valor in gases_override.items():
                    gases[gas] = round(valor, 4)
                log.info(f"[SIM] {zona}: inicio perturbación '{tipo}' "
                         f"({config['descripcion']}) por {duracion} ciclos")
                return gases, tipo

        return gases, "normal"

    # ── Incidentes críticos ────────────────────────────────────────────────────
    def _inyectar_incidente(self, gases: dict, geo: dict) -> tuple[dict, dict, str]:
        """Inyecta un incidente crítico ponderado por severidad."""
        incidente = random.choices(INCIDENTES, weights=PESOS_INCIDENTES, k=1)[0]
        tipo = incidente["tipo"]

        zona_actual = next(iter(self._estado_actual), None)
        for gas, (lo, hi) in incidente["gases"].items():
            val = round(random.uniform(lo, hi), 4)
            gases[gas] = val
            # Actualizar estado para que la recuperación sea gradual
            if zona_actual and zona_actual in self._estado_actual:
                self._estado_actual[zona_actual][gas] = val

        # Incidentes geomecánicos asociados
        if tipo in ("explosion_polvo_carbon", "escape_ch4_masivo"):
            geo["vibracion_mms"]      = round(random.uniform(25, 60), 1)
            geo["indice_estabilidad"] = round(random.uniform(0.15, 0.40), 3)

        log.warning(f"[SIM] ⚠ INCIDENTE: {incidente['descripcion']} "
                    f"| Nivel esperado: {incidente['nivel_esperado']}")
        return gases, geo, tipo

    # ── Ciclo principal ────────────────────────────────────────────────────────
    async def _enviar_ciclo(self, zona: str, forzar_evento: bool = False) -> dict:
        """Genera datos y los envía al Orquestador."""
        gases       = self._lectura_gas_normal(zona)
        geo         = self._lectura_geo_normal(zona)
        imagen      = self._deteccion_visual()
        tipo_evento = "normal"

        # Probabilidades:
        #   5%  → incidente crítico (PRECAUCIÓN a EVACUACIÓN)
        #  15%  → perturbación operacional (INFORMATIVO)
        #  80%  → operación normal (SEGURO)
        r = random.random()
        if forzar_evento or r < 0.05:
            # Pasar zona para que _inyectar_incidente actualice el estado correcto
            self._init_estado(zona)
            # Guardamos zona temporalmente para que _inyectar_incidente la use
            self._zona_en_curso = zona
            gases, geo, tipo_evento = self._inyectar_incidente(gases, geo)
            self._estado_actual[zona] = {g: gases[g] for g in gases}
        elif r < 0.20:
            gases, tipo_evento = self._aplicar_perturbacion(gases, zona)
        else:
            # Dar oportunidad a perturbación en curso aunque no caiga en el 15%
            if zona in self._perturbacion_activa:
                gases, tipo_evento = self._aplicar_perturbacion(gases, zona)

        payload = {"zona": zona, "gases": gases, "imagen": imagen, "geo": geo}

        try:
            url  = f"http://{settings.orquestador_host}:{settings.orquestador_port}/orquestar"
            resp = await self._client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            resultado  = resp.json()
            nivel      = resultado.get("nivel_global", "?")
            log.info(f"[SIM] Ciclo {self._ciclo} | {zona} | {tipo_evento} | Nivel: {nivel}")
            return resultado
        except Exception as e:
            log.error(f"[SIM] Error enviando ciclo: {e}")
            return {}

    async def ejecutar_ciclo_unico(
        self, zona: Optional[str] = None, forzar_evento: bool = False
    ) -> dict:
        async with httpx.AsyncClient() as client:
            self._client = client
            z = zona or settings.simulacion_zona_default
            return await self._enviar_ciclo(z, forzar_evento)

    async def ejecutar_continuo(
        self, zonas: Optional[list[str]] = None, max_ciclos: int = -1
    ) -> None:
        zonas_activas = zonas or list(settings.zonas)
        self._corriendo = True
        self._ciclo     = 0

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
from fastapi.middleware.cors import CORSMiddleware

sim_app = FastAPI(title="Simulador Sensores Minería", version="2.0.0")
sim_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
simulador = Simulador()


@sim_app.post("/simular")
async def simular_ciclo(zona: str = "Frente_A_Sogamoso", evento: bool = False):
    resultado = await simulador.ejecutar_ciclo_unico(zona, forzar_evento=evento)
    return {"zona": zona, "evento_forzado": evento, "resultado": resultado}


@sim_app.post("/iniciar")
async def iniciar_simulacion(max_ciclos: int = -1):
    asyncio.create_task(simulador.ejecutar_continuo(max_ciclos=max_ciclos))
    return {"estado": "simulacion_iniciada", "max_ciclos": max_ciclos}


@sim_app.post("/detener")
async def detener_simulacion():
    simulador.detener()
    return {"estado": "simulacion_detenida"}
