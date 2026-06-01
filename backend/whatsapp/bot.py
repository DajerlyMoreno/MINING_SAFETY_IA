"""
bot.py — Lógica del Bot Omnicanal (Capa 4).
Procesa mensajes entrantes de WhatsApp, responde en lenguaje natural
via LLM+RAG y difunde alertas críticas a números registrados.
Compatible con Twilio WhatsApp API y Meta Cloud API.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag
from backend.llm.llm_engine import llm

log = get_logger("whatsapp_bot")

# ── Configuración desde .env ───────────────────────────────────────────────────
TWILIO_SID   = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM  = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

# Números de alerta separados por coma: +573001234567,+573009876543
NUMEROS_ALERTA: list[str] = [
    n.strip() for n in os.getenv("WHATSAPP_ALERTAS", "").split(",") if n.strip()
]

# Estado actual del sistema (actualizado por el orquestador)
ESTADO_SISTEMA: dict = {
    "nivel": "SEGURO",
    "zona":  "—",
    "ts":    "—",
}

# ── Respuestas predefinidas ────────────────────────────────────────────────────

AYUDA = """⛏ *Minería Subterránea IA — UPTC 2026*

Comandos disponibles:
• *estado* — nivel de riesgo en tiempo real
• *gases* — límites permisibles CH₄/CO/O₂/CO₂/H₂S
• *evacuacion* — protocolo completo de evacuación
• *sostenimiento* — reforzamiento de emergencia
• *ventilacion* — cumplimiento plan de ventilación
• *contactos* — ANM, emergencias y rescate
• O escribe tu pregunta directamente 📝"""

CONTACTOS = """📞 *Contactos de Emergencia — Boyacá:*
• Emergencias: *123*
• ANM Colombia: *57-1-3199099*
• SGC Sismicidad: *57-1-2200200*
• Defensa Civil: *144*
• Cruz Roja: *132*
• Bomberos: *119*"""

GASES_INFO = """🧪 *Límites Permisibles — Decreto 1886/2015:*
• *CH₄:* máx 0.5% (precaución), >1.5% EVACUACIÓN
• *CO:* máx 25 ppm (precaución), >200 ppm EVACUACIÓN
• *O₂:* mín 19.5% (precaución), <17% EVACUACIÓN
• *CO₂:* máx 0.5% (precaución), >3% EVACUACIÓN
• *H₂S:* máx 1 ppm (precaución), >10 ppm EVACUACIÓN"""

EVACUACION_BASICA = """🚨 *Protocolo de Evacuación (Art. 121 D.1886):*
1. Activar alarma: 3 pitidos cortos + 1 largo
2. Desplazarse CONTRA la corriente de ventilación
3. Usar auto-rescatador si hay presencia de gases
4. Punto de reunión: bocamina o zona segura designada
5. Reportar a superficie: jefe de turno → 123 → ANM
⚠️ NO reingresar sin autorización del ingeniero"""

SOSTENIMIENTO_BASICO = """🔩 *Sostenimiento de Emergencia (Art. 89 D.1886):*
1. Suspender avance INMEDIATAMENTE
2. Instalar cerchas adicionales cada 0.5 m en corona
3. Pernos de anclaje en zonas de fracturamiento
4. Cuneta de drenaje si hay presencia de agua
5. Notificar al ingeniero residente con registro
6. Registrar en libro de mina con fecha y firma"""

VENTILACION_INFO = """💨 *Plan de Ventilación (Art. 74 D.1886):*
• Caudal mínimo en frente: 6 m³/s
• Mínimo por trabajador: 0.25 m³/s
• Temperatura máxima: 26°C bulbo húmedo
• Velocidad mínima de aire: 0.3 m/s en galería
• Frecuencia de control: cada turno"""


class WhatsAppBot:
    """
    Bot omnicanal para notificaciones de seguridad minera.
    Opera con Twilio en producción y en modo simulación sin credenciales.
    """

    def __init__(self) -> None:
        self._con_twilio = bool(TWILIO_SID and TWILIO_TOKEN)
        if not self._con_twilio:
            log.warning(
                "Twilio no configurado — bot en modo SIMULACIÓN. "
                "Agrega TWILIO_ACCOUNT_SID y TWILIO_AUTH_TOKEN al .env"
            )

    # ── Procesamiento de mensajes entrantes ────────────────────────────────────

    async def procesar(self, de: str, cuerpo: str) -> str:
        texto = cuerpo.strip().lower()

        # Comandos fijos
        if texto in ("ayuda", "help", "/ayuda", "/start", "hola", "inicio"):
            return AYUDA
        if texto in ("contactos", "anm", "emergencias"):
            return CONTACTOS
        if texto in ("gases", "gas", "metano", "ch4"):
            return GASES_INFO
        if texto in ("evacuacion", "evacuación", "evacuar"):
            docs = rag.consultar("evacuación protocolo inmediata decreto 1886", k=3)
            if docs:
                frags = "\n".join(f"• {d['titulo']}: {d.get('contenido','')[:150]}" for d in docs)
                return f"🚨 *Protocolo de Evacuación (RAG — Decreto 1886/2015):*\n\n{frags}"
            return EVACUACION_BASICA
        if texto in ("sostenimiento", "soporte", "cerchas", "pernos"):
            return SOSTENIMIENTO_BASICO
        if texto in ("ventilacion", "ventilación"):
            return VENTILACION_INFO
        if texto in ("estado", "status"):
            return self._estado_msg()

        # Consulta libre → RAG + LLM
        docs  = rag.consultar(cuerpo, k=3)
        estado_txt = f"Zona: {ESTADO_SISTEMA['zona']}, Nivel: {ESTADO_SISTEMA['nivel']}"
        respuesta = await llm.responder_consulta(cuerpo, docs, estado_txt)
        # WhatsApp limita a ~1600 chars
        return respuesta[:1500]

    def _estado_msg(self) -> str:
        nivel = ESTADO_SISTEMA["nivel"]
        emoji = {
            "SEGURO":                "🟢",
            "INFORMATIVO":           "🔵",
            "PRECAUCIÓN":            "🟡",
            "RIESGO ALTO":           "🟠",
            "EMERGENCIA":            "🔴",
            "EVACUACIÓN INMEDIATA":  "🚨",
        }.get(nivel, "⚪")
        return (
            f"{emoji} *Estado del Sistema:*\n"
            f"Zona activa: {ESTADO_SISTEMA['zona']}\n"
            f"Nivel global: *{nivel}*\n"
            f"Actualizado: {ESTADO_SISTEMA['ts']}"
        )

    # ── Envío de mensajes ──────────────────────────────────────────────────────

    async def enviar(self, numero: str, mensaje: str) -> bool:
        """Envía un mensaje WhatsApp a un número via Twilio."""
        if not self._con_twilio:
            log.info(f"[SIM WhatsApp] → {numero}: {mensaje[:80]}…")
            return True
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
                    data={
                        "From": TWILIO_FROM,
                        "To":   f"whatsapp:{numero}",
                        "Body": mensaje,
                    },
                    auth=(TWILIO_SID, TWILIO_TOKEN),
                    timeout=10.0,
                )
                ok = resp.status_code == 201
                if not ok:
                    log.error(f"Twilio error {resp.status_code}: {resp.text[:200]}")
                return ok
        except Exception as e:
            log.error(f"Error enviando WhatsApp a {numero}: {e}")
            return False

    async def difundir_alerta(
        self, zona: str, nivel: str, acciones: list[str], diagnostico: str
    ) -> None:
        """Difunde alerta crítica a todos los números registrados en .env."""
        ESTADO_SISTEMA.update({
            "nivel": nivel,
            "zona":  zona,
            "ts":    datetime.now(timezone.utc).strftime("%H:%M UTC"),
        })

        if not NUMEROS_ALERTA:
            log.info("Sin números WhatsApp registrados — alerta simulada en log")
            log.warning(f"ALERTA {nivel} | {zona} | {diagnostico[:100]}")
            return

        acciones_txt = "\n".join(f"• {a}" for a in acciones[:3])
        mensaje = (
            f"🚨 *ALERTA MINERÍA IA — {zona}*\n"
            f"Nivel: *{nivel}*\n\n"
            f"📋 {diagnostico[:250]}\n\n"
            f"⚡ *Acciones:*\n{acciones_txt}\n\n"
            f"📞 Emergencias: 123 | ANM: 3199099"
        )

        resultados = await asyncio.gather(
            *[self.enviar(num, mensaje) for num in NUMEROS_ALERTA],
            return_exceptions=True,
        )
        exitos = sum(1 for r in resultados if r is True)
        log.info(f"Alertas WhatsApp enviadas: {exitos}/{len(NUMEROS_ALERTA)}")


# Instancia global singleton
bot = WhatsAppBot()
