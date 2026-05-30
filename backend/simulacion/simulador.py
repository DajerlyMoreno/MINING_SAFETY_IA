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
    """
    Generador de datos sintéticos con:
      - Proceso AR(1) para continuidad temporal (sin saltos bruscos)
      - Sistema de targets: incidentes y perturbaciones fijan un objetivo
        al que el AR(1) converge gradualmente (subida y bajada suaves)
      - Correlaciones físicas entre gases (combustión, desplazamiento de O2)
    """

    _ALPHA = 0.74   # inercia temporal: 74% valor anterior, 26% objetivo

    def __init__(self) -> None:
        self._corriendo = False
        self._ciclo     = 0
        self._client: Optional[httpx.AsyncClient] = None
        # Estado actual medido por zona (valor del ciclo anterior)
        self._estado_actual:   dict = {}
        # Target actual por zona y gas (None = usar línea base del perfil)
        self._target_gases:    dict = {}
        # Perturbación activa por zona
        self._perturbacion_activa: dict = {}

    # ── Inicialización de estado ───────────────────────────────────────────────
    def _init_estado(self, zona: str) -> None:
        if zona not in self._estado_actual:
            perfil = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
            self._estado_actual[zona] = {
                g: float(np.random.normal(mu, sigma * 0.4))
                for g, (mu, sigma) in perfil.items()
            }

    def _set_target(self, zona: str, gases_target: dict) -> None:
        """Fija el objetivo al que convergerá el AR(1) para gases específicos."""
        if zona not in self._target_gases:
            self._target_gases[zona] = {}
        self._target_gases[zona].update(gases_target)

    def _clear_target(self, zona: str, gases: list | None = None) -> None:
        """Limpia targets (vuelve a la línea base). gases=None limpia todos."""
        if zona not in self._target_gases:
            return
        if gases is None:
            del self._target_gases[zona]
        else:
            for g in gases:
                self._target_gases[zona].pop(g, None)
            if not self._target_gases[zona]:
                del self._target_gases[zona]

    # ── AR(1) con target dinámico ──────────────────────────────────────────────
    def _lectura_gas_normal(self, zona: str) -> dict:
        """
        Proceso AR(1) con target dinámico:
          nuevo = alpha * anterior + (1-alpha) * objetivo + ruido_sensor

        El objetivo puede ser la línea base del perfil (operación normal) o
        un valor de incidente/perturbación fijado con _set_target().
        Esto garantiza subidas y bajadas siempre graduales.
        """
        self._init_estado(zona)
        perfil  = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
        previo  = self._estado_actual[zona]
        targets = self._target_gases.get(zona, {})
        alpha   = self._ALPHA
        gases   = {}

        for gas, (mu, sigma) in perfil.items():
            # Objetivo: target activo si existe, si no la línea base
            target   = targets.get(gas, mu)
            objetivo = float(np.random.normal(target, sigma * 0.15))
            # AR(1): mezcla suave con el valor anterior
            nuevo    = alpha * previo[gas] + (1.0 - alpha) * objetivo
            # Ruido mínimo de sensor
            nuevo   += float(np.random.normal(0.0, sigma * 0.04))
            if gas == "O2":
                nuevo = float(np.clip(nuevo, 15.0, 21.0))
            else:
                nuevo = float(np.clip(nuevo, 0.0, None))
            gases[gas] = round(nuevo, 4)

        # Aplicar correlaciones físicas entre gases
        gases = self._aplicar_correlaciones(gases, zona)

        self._estado_actual[zona] = dict(gases)
        return gases

    # ── Correlaciones físicas ──────────────────────────────────────────────────
    def _aplicar_correlaciones(self, gases: dict, zona: str) -> dict:
        """
        Correlaciones basadas en química minera:

        COMBUSTIÓN (CO↑ → CO2↑ + O2↓):
          Equipos diésel, incendios y voladuras consumen O2 y producen CO y CO2.
          Stoichiometry: 2CO + O2 → 2CO2

        DESPLAZAMIENTO (CH4↑ / CO2↑ → O2↓):
          Los gases pesados desplazan el O2 en zonas bajas.

        OXIDACIÓN PARCIAL DE CH4 (CH4 alto → CO↑):
          En atmósferas pobres en O2, la oxidación incompleta genera CO.
        """
        perfil   = PERFILES_ZONA.get(zona, PERFILES_ZONA["Bocamina"])
        base_CO  = perfil["CO"][0]
        base_CH4 = perfil["CH4"][0]
        base_CO2 = perfil["CO2"][0]

        d_CO  = max(0.0, gases["CO"]  - base_CO)   # exceso de CO sobre línea base
        d_CH4 = max(0.0, gases["CH4"] - base_CH4)   # exceso de CH4
        d_CO2 = max(0.0, gases["CO2"] - base_CO2)   # exceso de CO2

        # 1. Combustión: CO↑ consume O2 y genera CO2
        delta_O2_combustion = -(d_CO * 0.0012)
        delta_CO2_combustion = d_CO * 0.0020

        # 2. Desplazamiento: CH4 y CO2 desplazan O2
        delta_O2_desplaz = -(d_CH4 * 0.55 + d_CO2 * 0.30)

        # 3. Oxidación parcial: CH4 muy alto + O2 bajo → algo de CO extra
        if gases["CH4"] > 0.9 and gases["O2"] < 20.0:
            extra_CO = (gases["CH4"] - 0.9) * 2.5
            gases["CO"] = round(min(gases["CO"] + extra_CO, 300.0), 4)

        # Aplicar correcciones a O2 y CO2
        nuevo_O2  = gases["O2"]  + delta_O2_combustion + delta_O2_desplaz
        nuevo_CO2 = gases["CO2"] + delta_CO2_combustion

        gases["O2"]  = round(float(np.clip(nuevo_O2,  15.0, 21.0)), 4)
        gases["CO2"] = round(float(np.clip(nuevo_CO2,  0.0,  5.0)), 4)

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

    # ── Perturbaciones: fijan target, el AR(1) converge gradualmente ──────────
    def _aplicar_perturbacion(self, zona: str) -> str:
        """
        Gestiona perturbaciones operacionales usando el sistema de targets.
        No sobreescribe gases directamente — el AR(1) hace la transición.
        """
        estado = self._perturbacion_activa.get(zona)

        # Continuar perturbación en curso
        if estado and estado["ciclos_restantes"] > 0:
            estado["ciclos_restantes"] -= 1
            if estado["ciclos_restantes"] == 0:
                # Limpiar target: el AR(1) vuelve gradualmente a la línea base
                self._clear_target(zona, list(estado["gases_target"].keys()))
                del self._perturbacion_activa[zona]
                log.info(f"[SIM] {zona}: perturbación '{estado['tipo']}' terminando — recuperación gradual")
            return estado["tipo"]

        # Evaluar inicio de nueva perturbación
        for tipo, config in PERTURBACIONES.items():
            if random.random() < config["prob"]:
                duracion = random.randint(*config["duracion_ciclos"])
                gases_target = {
                    gas: random.uniform(lo, hi)
                    for gas, (lo, hi) in config["gases"].items()
                }
                self._perturbacion_activa[zona] = {
                    "tipo":            tipo,
                    "gases_target":    gases_target,
                    "ciclos_restantes": duracion,
                }
                # Fijar target: el AR(1) comenzará a subir hacia estos valores
                self._set_target(zona, gases_target)
                log.info(f"[SIM] {zona}: inicio perturbación '{tipo}' "
                         f"({config['descripcion']}) por {duracion} ciclos")
                return tipo

        return "normal"

    # ── Incidentes: fijan target alto, el AR(1) sube gradualmente ─────────────
    def _inyectar_incidente(self, zona: str, geo: dict) -> tuple[dict, str]:
        """
        Inyecta incidente fijando targets elevados.
        La subida es gradual (AR(1)), no instantánea.
        Al ciclo siguiente sin incidente el AR(1) comenzará a bajar.
        """
        incidente = random.choices(INCIDENTES, weights=PESOS_INCIDENTES, k=1)[0]
        tipo      = incidente["tipo"]

        gases_target = {
            gas: random.uniform(lo, hi)
            for gas, (lo, hi) in incidente["gases"].items()
        }
        self._set_target(zona, gases_target)

        # Geomecánica asociada (efecto inmediato, no necesita suavizado)
        if tipo in ("explosion_polvo_carbon", "escape_ch4_masivo"):
            geo["vibracion_mms"]      = round(random.uniform(25, 60), 1)
            geo["indice_estabilidad"] = round(random.uniform(0.15, 0.40), 3)

        log.warning(f"[SIM] ⚠ INCIDENTE en {zona}: {incidente['descripcion']} "
                    f"| Target: {gases_target} | Nivel esperado: {incidente['nivel_esperado']}")
        return geo, tipo

    # ── Ciclo principal ────────────────────────────────────────────────────────
    async def _enviar_ciclo(self, zona: str, forzar_evento: bool = False) -> dict:
        """Genera datos con AR(1)+correlaciones y los envía al Orquestador."""
        self._init_estado(zona)
        geo         = self._lectura_geo_normal(zona)
        imagen      = self._deteccion_visual()
        tipo_evento = "normal"

        r = random.random()
        if forzar_evento or r < 0.05:
            geo, tipo_evento = self._inyectar_incidente(zona, geo)
        elif r < 0.20 or zona in self._perturbacion_activa:
            tipo_evento = self._aplicar_perturbacion(zona)
        else:
            # Sin evento: limpiar cualquier target residual de incidente anterior
            if zona in self._target_gases and zona not in self._perturbacion_activa:
                self._clear_target(zona)

        # Generar lectura con AR(1) y correlaciones (SIEMPRE gradual)
        gases = self._lectura_gas_normal(zona)

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
