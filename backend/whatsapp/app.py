"""
app.py — Bot Omnicanal WhatsApp (Puerto 8006) — Capa 4.
Webhooks para Twilio y Meta Cloud API.
Endpoint interno para alertas del orquestador/LangGraph.
Endpoint de chat web para pruebas sin WhatsApp real (dashboard).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from backend.shared.logger import get_logger
from backend.rag.rag_engine import rag
from backend.llm.llm_engine import llm
from backend.whatsapp.bot import bot, ESTADO_SISTEMA

log = get_logger("whatsapp_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=== Bot WhatsApp iniciando en :8006 ===")
    rag.inicializar()
    llm.inicializar()
    log.info(f"Bot WhatsApp listo | LLM: {'Gemini' if llm.operativo else 'Fallback'}")
    yield
    log.info("=== Bot WhatsApp detenido ===")


app = FastAPI(
    title="💬 Bot Omnicanal MinEría IA — UPTC 2026",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


# ── Webhook Twilio ─────────────────────────────────────────────────────────────

@app.post("/webhook/twilio", response_class=PlainTextResponse)
async def webhook_twilio(
    Body: str = Form(default=""),
    From: str = Form(default=""),
):
    """Webhook compatible con Twilio WhatsApp API (formato TwiML)."""
    log.info(f"Twilio mensaje: {From} → {Body[:80]}")
    respuesta = await bot.procesar(From, Body)
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{respuesta}</Message></Response>"
    )
    return twiml


# ── Webhook Meta Cloud API ─────────────────────────────────────────────────────

@app.post("/webhook/meta")
async def webhook_meta(request: Request):
    """Webhook compatible con Meta WhatsApp Cloud API."""
    data = await request.json()
    try:
        entry   = data["entry"][0]["changes"][0]["value"]
        msg     = entry["messages"][0]
        de      = msg["from"]
        texto   = msg["text"]["body"]
        log.info(f"Meta mensaje: {de} → {texto[:80]}")
        respuesta = await bot.procesar(de, texto)
        return {"status": "ok", "respuesta_enviada": respuesta[:100]}
    except (KeyError, IndexError):
        return {"status": "ignored"}


@app.get("/webhook/meta")
async def verificar_meta(
    hub_mode: str = "",
    hub_challenge: str = "",
    hub_verify_token: str = "",
):
    """Verificación del webhook de Meta (challenge-response)."""
    token_esperado = os.getenv("META_VERIFY_TOKEN", "mineria_ia_2026")
    if hub_mode == "subscribe" and hub_verify_token == token_esperado:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "Token de verificación Meta inválido")


# ── Alerta interna del orquestador / LangGraph ─────────────────────────────────

class AlertaInterna(BaseModel):
    zona:         str       = Field(example="Frente_A_Sogamoso")
    nivel:        str       = Field(example="EMERGENCIA")
    correlaciones: list[str] = Field(default_factory=list)
    acciones:     list[str] = Field(default_factory=list)
    diagnostico:  str       = Field(default="")
    evento_id:    str       = Field(example="A3F1B2")


@app.post("/alertar_interno")
async def alertar_interno(alerta: AlertaInterna):
    """
    El nodo nodo_emitir_alerta del grafo LangGraph llama a este endpoint
    cuando el nivel global >= EMERGENCIA para disparar alertas WhatsApp.
    """
    ESTADO_SISTEMA.update({"nivel": alerta.nivel, "zona": alerta.zona})
    await bot.difundir_alerta(
        zona=alerta.zona,
        nivel=alerta.nivel,
        acciones=alerta.acciones,
        diagnostico=alerta.diagnostico,
    )
    return {"status": "ok", "evento_id": alerta.evento_id}


# ── Chat web (simulación WhatsApp para el dashboard) ──────────────────────────

class MensajeChat(BaseModel):
    mensaje: str  = Field(example="¿Qué hago si el CH4 supera 2%?")
    usuario: str  = Field(default="web_user")


@app.post("/chat")
async def chat_web(req: MensajeChat):
    """
    Endpoint de chat web — permite probar el bot desde el dashboard React
    sin necesidad de WhatsApp real. Usa el mismo pipeline LLM+RAG.
    """
    respuesta = await bot.procesar(req.usuario, req.mensaje)
    return {
        "respuesta":     respuesta,
        "estado_actual": ESTADO_SISTEMA,
        "llm_activo":    llm.operativo,
    }


# ── Estado del bot ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "agente":        "BOT_WHATSAPP",
        "estado":        "ACTIVO",
        "puerto":        8006,
        "llm_activo":    llm.operativo,
        "twilio_activo": bot._con_twilio,
        "numeros_alerta": len(bot.__class__.__module__ and []),
    }


@app.get("/estado")
async def estado_bot():
    return {
        "estado_sistema": ESTADO_SISTEMA,
        "llm_activo":     llm.operativo,
        "twilio_activo":  bot._con_twilio,
    }
