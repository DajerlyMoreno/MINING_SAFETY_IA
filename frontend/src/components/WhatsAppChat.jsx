/**
 * WhatsAppChat.jsx — Simulación del Bot WhatsApp en el dashboard.
 * Permite probar el bot omnicanal sin necesidad de WhatsApp real.
 * Usa el endpoint /chat del bot (puerto 8006).
 */

import React, { useState, useRef, useEffect } from "react";

const BOT_URL = import.meta.env.VITE_BOT_WA || "http://localhost:8006";

const SUGERENCIAS = [
  "estado",
  "evacuar",
  "gases",
  "sostenimiento",
  "ventilacion",
  "contactos",
  "¿Qué hago si el CH₄ llega al 2%?",
  "¿Cómo activo el plan de emergencia?",
];

// ─── Burbuja de mensaje ───────────────────────────────────────────────────────
function Burbuja({ msg }) {
  const esBot = msg.de === "bot";
  return (
    <div className={`flex ${esBot ? "justify-start" : "justify-end"} mb-2`}>
      {esBot && (
        <div className="w-7 h-7 rounded-full bg-green-700 flex items-center justify-center
                        text-xs font-bold mr-2 mt-1 shrink-0">
          IA
        </div>
      )}
      <div
        className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap
          ${esBot
            ? "bg-gray-800 text-gray-100 rounded-tl-none border border-gray-700"
            : "bg-green-700 text-white rounded-tr-none"
          }`}
      >
        {msg.texto}
        <p className={`text-[10px] mt-1 ${esBot ? "text-gray-500" : "text-green-300"} text-right`}>
          {msg.hora}
        </p>
      </div>
    </div>
  );
}

// ─── Panel principal ───────────────────────────────────────────────────────────
export function WhatsAppChat() {
  const [mensajes, setMensajes]  = useState([
    {
      de:    "bot",
      texto: "⛏ *Minería Subterránea IA — UPTC 2026*\n\nEscribe tu consulta o usa un comando:\n• *estado* — riesgo actual\n• *evacuacion* — protocolo\n• *gases* — límites permisibles\n• *contactos* — ANM y emergencias",
      hora:  new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input,    setInput]    = useState("");
  const [enviando, setEnviando] = useState(false);
  const [botInfo,  setBotInfo]  = useState(null);
  const bottomRef = useRef(null);

  // Cargar estado del bot
  useEffect(() => {
    const cargar = async () => {
      try {
        const r = await fetch(`${BOT_URL}/estado`);
        if (r.ok) setBotInfo(await r.json());
      } catch { /* bot offline */ }
    };
    cargar();
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes]);

  const hora = () =>
    new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });

  const enviar = async (texto) => {
    const msg = texto || input.trim();
    if (!msg || enviando) return;
    setInput("");

    // Agregar mensaje del usuario
    setMensajes((prev) => [...prev, { de: "user", texto: msg, hora: hora() }]);
    setEnviando(true);

    try {
      const r = await fetch(`${BOT_URL}/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ mensaje: msg, usuario: "dashboard_user" }),
      });
      const d = await r.json();
      setMensajes((prev) => [
        ...prev,
        { de: "bot", texto: d.respuesta, hora: hora() },
      ]);
      if (d.estado_actual) setBotInfo({ estado_sistema: d.estado_actual, llm_activo: d.llm_activo });
    } catch {
      setMensajes((prev) => [
        ...prev,
        {
          de:    "bot",
          texto: "⚠️ Bot WhatsApp no disponible (puerto 8006).\nEjecuta: backend.whatsapp.app:app",
          hora:  hora(),
        },
      ]);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <div className="flex flex-col lg:flex-row gap-4">

      {/* ── Chat principal ───────────────────────────────────────────────── */}
      <div className="flex-1 bg-gray-900 rounded-xl border border-gray-700 flex flex-col"
           style={{ height: "600px" }}>

        {/* Header estilo WhatsApp */}
        <div className="flex items-center gap-3 p-3 bg-green-900 rounded-t-xl border-b border-green-800">
          <div className="w-9 h-9 rounded-full bg-green-600 flex items-center justify-center font-bold">
            ⛏
          </div>
          <div className="flex-1">
            <p className="font-bold text-sm">Minería IA Bot</p>
            <p className="text-xs text-green-300">
              {botInfo?.llm_activo ? "🟢 Gemini activo" : "🟡 Modo fallback"}
              {botInfo?.estado_sistema?.nivel &&
                ` · Nivel: ${botInfo.estado_sistema.nivel}`}
            </p>
          </div>
          <span className="text-xs text-green-400 bg-green-800 px-2 py-1 rounded">
            Simulación Web
          </span>
        </div>

        {/* Mensajes */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1"
             style={{ background: "repeating-linear-gradient(transparent, transparent 39px, #1f2937 39px, #1f2937 40px)" }}>
          {mensajes.map((m, i) => (
            <Burbuja key={i} msg={m} />
          ))}
          {enviando && (
            <div className="flex justify-start mb-2">
              <div className="bg-gray-800 rounded-2xl rounded-tl-none px-4 py-2 text-sm
                              border border-gray-700 text-gray-400 italic">
                Escribiendo…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="p-3 border-t border-gray-700 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && enviar()}
            placeholder="Escribe un mensaje o comando…"
            className="flex-1 bg-gray-800 border border-gray-600 rounded-full px-4 py-2
                       text-sm text-white placeholder-gray-500 focus:outline-none
                       focus:border-green-500"
          />
          <button
            onClick={() => enviar()}
            disabled={enviando || !input.trim()}
            className="w-10 h-10 rounded-full bg-green-600 hover:bg-green-500
                       disabled:opacity-40 disabled:cursor-not-allowed
                       flex items-center justify-center transition-colors"
          >
            ➤
          </button>
        </div>
      </div>

      {/* ── Panel lateral: sugerencias + estado ─────────────────────────── */}
      <div className="lg:w-64 space-y-4">

        {/* Comandos rápidos */}
        <div className="bg-gray-900 rounded-xl p-3 border border-gray-700">
          <h3 className="font-bold text-xs text-gray-400 uppercase tracking-wide mb-2">
            Comandos rápidos
          </h3>
          <div className="space-y-1">
            {SUGERENCIAS.map((s) => (
              <button
                key={s}
                onClick={() => enviar(s)}
                className="w-full text-left text-xs py-1.5 px-2 rounded-lg
                           bg-gray-800 hover:bg-gray-700 text-gray-300
                           transition-colors border border-gray-700"
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Estado del bot */}
        <div className="bg-gray-900 rounded-xl p-3 border border-gray-700">
          <h3 className="font-bold text-xs text-gray-400 uppercase tracking-wide mb-2">
            Estado del Bot
          </h3>
          <div className="space-y-1.5 text-xs">
            <div className="flex justify-between">
              <span className="text-gray-400">Puerto</span>
              <span className="text-white">8006</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">LLM</span>
              <span className={botInfo?.llm_activo ? "text-green-400" : "text-yellow-400"}>
                {botInfo?.llm_activo ? "Gemini ✓" : "Fallback"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Twilio</span>
              <span className={botInfo?.twilio_activo ? "text-green-400" : "text-gray-500"}>
                {botInfo?.twilio_activo ? "Activo ✓" : "Sin config"}
              </span>
            </div>
            {botInfo?.estado_sistema && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-400">Zona</span>
                  <span className="text-blue-400 truncate ml-2">
                    {botInfo.estado_sistema.zona}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Nivel</span>
                  <span className="text-orange-300">{botInfo.estado_sistema.nivel}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Configuración */}
        <div className="bg-gray-900 rounded-xl p-3 border border-gray-700 text-xs text-gray-500">
          <p className="font-medium text-gray-400 mb-1">📱 WhatsApp Real:</p>
          <p>Agrega al <code className="bg-gray-800 px-1 rounded">.env</code>:</p>
          <p className="mt-1 font-mono text-green-400">TWILIO_ACCOUNT_SID=…</p>
          <p className="font-mono text-green-400">TWILIO_AUTH_TOKEN=…</p>
          <p className="font-mono text-green-400">WHATSAPP_ALERTAS=+57…</p>
        </div>
      </div>
    </div>
  );
}
