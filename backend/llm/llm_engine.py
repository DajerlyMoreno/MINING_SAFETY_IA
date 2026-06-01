"""
llm_engine.py — Motor LLM para razonamiento contextual (Capa 2).
Usa Google Gemini (gratuito) como proveedor principal.
Fallback a respuestas basadas en plantillas si no hay API key.
Configura GEMINI_API_KEY en el archivo .env del proyecto.
"""

from __future__ import annotations

import asyncio
import os
from typing import Optional

from backend.shared.logger import get_logger

log = get_logger("llm_engine")

# ── Prompts del sistema ────────────────────────────────────────────────────────

_PROMPT_DIAGNOSTICO = """Eres un experto en seguridad minera subterránea colombiana, \
especializado en el Decreto 1886 de 2015 (Reglamento de Seguridad en Labores Mineras \
Subterráneas). Analiza la situación en tiempo real y genera un diagnóstico técnico.

ZONA MINERA: {zona}
NIVEL DE RIESGO GLOBAL: {nivel_riesgo}
CORRELACIONES DETECTADAS: {correlaciones}

LECTURAS DE SENSORES:
{lecturas}

HISTORIAL RECIENTE DE NIVELES: {historial}

NORMATIVA RECUPERADA (fragmentos RAG):
{normativa}

Responde EXACTAMENTE con este formato (sin texto adicional antes o después):
DIAGNÓSTICO: [2-3 oraciones técnicas explicando la causa probable del riesgo basada en los datos]
ACCIONES INMEDIATAS:
1. [acción más urgente y específica]
2. [segunda acción prioritaria]
3. [tercera acción de soporte]
REFERENCIA NORMATIVA: [artículo específico del Decreto 1886/2015 aplicable]
PRONÓSTICO: [evolución esperada en los próximos 30 min si no se interviene]"""

_PROMPT_CONSULTA = """Eres un asistente experto en seguridad minera subterránea colombiana \
que responde consultas del personal de mina y jefes de turno. Usa el Decreto 1886 de 2015 \
como referencia principal.

CONSULTA: {consulta}

CONTEXTO NORMATIVO (fragmentos recuperados):
{normativa}

ESTADO ACTUAL DEL SISTEMA: {estado}

Responde en español de forma clara, concisa y técnicamente precisa (máximo 3 párrafos).
Si implica una emergencia, empieza con: ⚠️ EMERGENCIA:
Cita el artículo específico del Decreto 1886/2015 cuando sea relevante."""


class LLMEngine:
    """
    Motor LLM singleton.
    - Primario: Google Gemini 1.5 Flash (requiere GEMINI_API_KEY en .env)
    - Fallback: respuestas basadas en plantillas estructuradas (sin API key)
    """

    _instance: Optional["LLMEngine"] = None

    def __new__(cls) -> "LLMEngine":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._inicializado = False
            cls._instance._model = None
        return cls._instance

    def inicializar(self) -> None:
        if self._inicializado:
            return
        self._model          = None
        self._genai_client   = None
        self._ultimo_error   = ""
        self._api_key_existe = False
        api_key = os.getenv("GEMINI_API_KEY", "").strip()

        if api_key:
            self._api_key_existe = True
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=api_key)
                self._model = "gemini-flash-latest"
                log.info("LLM Engine: Gemini Flash latest cliente creado — clave detectada")
            except Exception as e:
                self._ultimo_error = str(e)
                log.warning(f"No se pudo crear cliente Gemini: {e}. Modo fallback activo.")
        else:
            log.warning(
                "GEMINI_API_KEY no configurada. "
                "Agrega GEMINI_API_KEY=AIzaSy... al archivo .env"
            )

        self._inicializado = True

    @property
    def operativo(self) -> bool:
        return self._genai_client is not None and self._model is not None

    @property
    def estado(self) -> dict:
        return {
            "operativo":       self.operativo,
            "api_key_existe":  getattr(self, "_api_key_existe", False),
            "modelo":          self._model or "—",
            "ultimo_error":    getattr(self, "_ultimo_error", ""),
        }

    # ── Razonamiento diagnóstico ───────────────────────────────────────────────

    async def razonar_diagnostico(
        self,
        zona: str,
        nivel_riesgo: str,
        correlaciones: list[str],
        lecturas: dict,
        normativa_docs: list[dict],
        historial_niveles: list[str],
    ) -> dict:
        """
        Genera diagnóstico técnico multimodal usando LLM.
        Retorna dict con diagnostico, acciones_llm, referencia, pronostico.
        """
        if not self.operativo:
            return self._fallback_diagnostico(zona, nivel_riesgo, correlaciones)

        normativa_txt = "\n".join(
            f"• {d['titulo']}: {d.get('contenido', '')[:200]}"
            for d in normativa_docs[:3]
        ) or "No disponible en corpus."

        lecturas_txt = "\n".join(
            f"  {k}: {_fmt(v)}" for k, v in lecturas.items() if isinstance(v, dict)
            for k2, v2 in v.items()
            if not isinstance(v2, dict)
        ) or "\n".join(f"  {k}: {_fmt(v)}" for k, v in lecturas.items())

        historial_txt = " → ".join(historial_niveles[-6:]) if historial_niveles else "Sin historial previo"

        prompt = _PROMPT_DIAGNOSTICO.format(
            zona=zona,
            nivel_riesgo=nivel_riesgo,
            correlaciones="; ".join(correlaciones) or "Ninguna correlación multiagente crítica",
            lecturas=lecturas_txt,
            historial=historial_txt,
            normativa=normativa_txt,
        )

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config={"temperature": 0.25, "max_output_tokens": 700},
            )
            self._ultimo_error = ""
            return _parsear_respuesta(response.text)
        except Exception as e:
            self._ultimo_error = str(e)
            log.error(f"Error Gemini en diagnóstico: {e}")
            return self._fallback_diagnostico(zona, nivel_riesgo, correlaciones)

    # ── Consulta de lenguaje natural ───────────────────────────────────────────

    async def responder_consulta(
        self,
        consulta: str,
        normativa_docs: list[dict],
        estado_actual: str,
    ) -> str:
        """
        Responde consulta en lenguaje natural (WhatsApp / chat web).
        """
        if not self.operativo:
            return _fallback_consulta(consulta)

        normativa_txt = "\n".join(
            f"• {d['titulo']}: {d.get('contenido', '')[:300]}"
            for d in normativa_docs[:3]
        ) or "Decreto 1886/2015 — Reglamento de Seguridad en Labores Mineras Subterráneas."

        prompt = _PROMPT_CONSULTA.format(
            consulta=consulta,
            normativa=normativa_txt,
            estado=estado_actual,
        )

        try:
            response = await self._genai_client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config={"temperature": 0.3, "max_output_tokens": 500},
            )
            self._ultimo_error = ""
            return response.text.strip()[:1400]
        except Exception as e:
            self._ultimo_error = str(e)
            log.error(f"Error Gemini en consulta: {e}")
            return _fallback_error_api(consulta, str(e))

    # ── Fallback ───────────────────────────────────────────────────────────────

    def _fallback_diagnostico(
        self, zona: str, nivel: str, correlaciones: list[str]
    ) -> dict:
        corr = "; ".join(correlaciones) if correlaciones else "monitoreo de rutina"
        return {
            "diagnostico": (
                f"Análisis automático — {zona}: nivel {nivel}. "
                f"Correlaciones: {corr}. "
                "Verificación manual requerida por el jefe de turno."
            ),
            "acciones_llm": [
                "Verificar lecturas de sensores in situ con equipo portátil",
                "Notificar al jefe de turno y registrar en bitácora de mina",
                "Consultar Decreto 1886/2015 Arts. 120–130 para protocolo aplicable",
            ],
            "referencia": "Decreto 1886/2015 — Arts. 120-130 (Ventilación y Gases)",
            "pronostico": (
                "Evolución indeterminada sin LLM activo. "
                "Configure GEMINI_API_KEY en .env para diagnóstico inteligente."
            ),
            "texto_completo": "(Modo fallback — GEMINI_API_KEY no configurada)",
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(v) -> str:
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def _parsear_respuesta(texto: str) -> dict:
    """Extrae campos estructurados de la respuesta Gemini.
    Acumula TODAS las líneas del diagnóstico hasta encontrar la siguiente sección,
    evitando el corte prematuro cuando Gemini genera texto en varias líneas.
    """
    result: dict = {
        "diagnostico": "",
        "acciones_llm": [],
        "referencia": "",
        "pronostico": "",
        "texto_completo": texto,
    }
    seccion = None
    lineas_diag: list[str] = []

    for line in texto.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("DIAGNÓSTICO:"):
            primera = line.removeprefix("DIAGNÓSTICO:").strip()
            if primera:
                lineas_diag.append(primera)
            seccion = "diagnostico"
        elif line.startswith("ACCIONES INMEDIATAS"):
            seccion = "acciones"
        elif line.startswith("REFERENCIA NORMATIVA:"):
            result["referencia"] = line.removeprefix("REFERENCIA NORMATIVA:").strip()
            seccion = None
        elif line.startswith("PRONÓSTICO:"):
            result["pronostico"] = line.removeprefix("PRONÓSTICO:").strip()
            seccion = None
        elif seccion == "diagnostico":
            # Acumular continuaciones del diagnóstico (texto multilinea de Gemini)
            lineas_diag.append(line)
        elif seccion == "acciones" and line and line[0].isdigit():
            accion = line.lstrip("0123456789. ").strip()
            if accion:
                result["acciones_llm"].append(accion)

    # Unir todas las líneas del diagnóstico
    if lineas_diag:
        result["diagnostico"] = " ".join(lineas_diag)
    if not result["diagnostico"]:
        result["diagnostico"] = texto[:500]
    return result


def _fallback_consulta(consulta: str) -> str:
    return (
        f"Consulta: '{consulta}'\n\n"
        "⚠️ LLM no disponible: GEMINI_API_KEY no configurada en el archivo .env.\n"
        "Obtén tu clave gratuita en: https://aistudio.google.com/apikey\n\n"
        "Referencia rápida — Decreto 1886/2015:\n"
        "• Art. 120: CH₄ máx 1% (precaución), 1.5% EVACUACIÓN\n"
        "• Art. 123: CO máx 25 ppm (precaución), 200 ppm EVACUACIÓN\n"
        "• Art. 118: O₂ mín 19.5%, <17.5% EVACUACIÓN\n"
        "• Art. 121: Protocolo de evacuación — 3 pitidos + 1 largo\n\n"
        "📞 Emergencias: 123 | ANM: 57-1-3199099"
    )


def _fallback_error_api(consulta: str, error: str) -> str:
    """Fallback específico cuando la API falla (clave inválida, cuota, red)."""
    if "429" in error or "RESOURCE_EXHAUSTED" in error or "quota" in error.lower():
        causa = (
            "⚠️ Cuota de Gemini agotada (error 429).\n"
            "Soluciones:\n"
            "• Espera unos minutos (límite: 15 req/min en plan gratuito)\n"
            "• Genera una nueva clave en https://aistudio.google.com/apikey\n"
            "• Verifica que la clave comience con 'AIzaSy...'"
        )
    elif "401" in error or "403" in error or "API_KEY" in error or "invalid" in error.lower():
        causa = (
            "⚠️ Clave Gemini inválida o sin permisos.\n"
            "Verifica que:\n"
            "• La clave en .env comience con 'AIzaSy...'\n"
            "• La obteniste desde https://aistudio.google.com/apikey\n"
            "• No tiene espacios extra al pegarla"
        )
    else:
        causa = f"⚠️ Error de conexión con Gemini: {error[:120]}"

    return (
        f"{causa}\n\n"
        f"Consulta recibida: '{consulta}'\n\n"
        "Referencia rápida — Decreto 1886/2015:\n"
        "• Art. 120: CH₄ máx 1% (precaución), 1.5% EVACUACIÓN\n"
        "• Art. 123: CO máx 25 ppm, 200 ppm EVACUACIÓN\n"
        "• Art. 118: O₂ mín 19.5%, <17.5% EVACUACIÓN\n"
        "• Art. 121: Protocolo de evacuación\n\n"
        "📞 Emergencias: 123 | ANM: 57-1-3199099"
    )


# Instancia global singleton
llm = LLMEngine()
