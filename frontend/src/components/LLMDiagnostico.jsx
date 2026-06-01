/**
 * LLMDiagnostico.jsx — Panel de diagnóstico generado por Gemini + RAG.
 * Muestra el razonamiento LLM del último evento procesado por LangGraph.
 */

import React, { useState, useEffect } from "react";

const ORQUESTADOR = import.meta.env.VITE_ORQUESTADOR || "http://localhost:8000";
const ZONAS = ["Frente_A_Sogamoso", "Frente_B_Mongua", "Galeria_Central", "Bocamina"];

// ─── Estado del LLM ──────────────────────────────────────────────────────────
function EstadoLLM({ llmActivo, ultimoError }) {
  if (llmActivo === null) return null;

  if (llmActivo) {
    return (
      <span className="text-xs px-2 py-0.5 rounded-full bg-green-800 text-green-300">
        Gemini activo
      </span>
    );
  }

  // No activo — mostrar causa
  let msg = "Sin clave GEMINI_API_KEY";
  let cls = "bg-gray-700 text-gray-300";
  if (ultimoError) {
    if (ultimoError.includes("429") || ultimoError.includes("RESOURCE_EXHAUSTED")) {
      msg = "Cuota agotada (429)";
      cls = "bg-orange-800 text-orange-200";
    } else if (ultimoError.includes("401") || ultimoError.includes("403") || ultimoError.includes("invalid")) {
      msg = "Clave inválida (401/403)";
      cls = "bg-red-800 text-red-200";
    } else {
      msg = "Error API";
      cls = "bg-red-800 text-red-200";
    }
  }
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full ${cls}`} title={ultimoError}>
      ⚠️ {msg}
    </span>
  );
}


// ─── Consulta libre al LLM ────────────────────────────────────────────────────
function PanelConsulta() {
  const [consulta,   setConsulta]   = useState("");
  const [respuesta,  setRespuesta]  = useState(null);
  const [cargando,   setCargando]   = useState(false);
  const [llmActivo,  setLlmActivo]  = useState(null);
  const [ultimoError, setUltimoError] = useState("");

  // Cargar estado real del LLM al montar
  useEffect(() => {
    const cargar = async () => {
      try {
        const r = await fetch(`${ORQUESTADOR}/llm/estado`);
        if (r.ok) {
          const d = await r.json();
          setLlmActivo(d.operativo);
          setUltimoError(d.ultimo_error || "");
        }
      } catch { /* orquestador offline */ }
    };
    cargar();
    const id = setInterval(cargar, 15_000);
    return () => clearInterval(id);
  }, []);

  const enviar = async () => {
    if (!consulta.trim()) return;
    setCargando(true);
    setRespuesta(null);
    try {
      const r = await fetch(`${ORQUESTADOR}/llm/consultar`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ consulta }),
      });
      const d = await r.json();
      setRespuesta(d);
      setLlmActivo(d.llm_activo);
    } catch {
      setRespuesta({ respuesta: "Error: orquestador no disponible", llm_activo: false });
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
      <h3 className="font-bold text-sm mb-3 flex items-center gap-2">
        🤖 Consulta al LLM
        <EstadoLLM llmActivo={llmActivo} ultimoError={ultimoError} />
      </h3>

      {/* Aviso de cuota agotada */}
      {ultimoError && (ultimoError.includes("429") || ultimoError.includes("RESOURCE_EXHAUSTED")) && (
        <div className="mb-3 bg-orange-950 border border-orange-700 rounded-lg p-2 text-xs text-orange-200">
          <strong>Cuota de Gemini agotada.</strong> Obtén una nueva clave gratuita en{" "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"
             className="underline text-orange-300">aistudio.google.com/apikey</a>{" "}
          y reemplaza <code className="bg-orange-900 px-1 rounded">GEMINI_API_KEY</code> en el archivo <code className="bg-orange-900 px-1 rounded">.env</code>.
        </div>
      )}
      {ultimoError && (ultimoError.includes("401") || ultimoError.includes("403")) && (
        <div className="mb-3 bg-red-950 border border-red-700 rounded-lg p-2 text-xs text-red-200">
          <strong>Clave inválida.</strong> La clave debe comenzar con <code>AIzaSy...</code> y obtenerse desde{" "}
          <a href="https://aistudio.google.com/apikey" target="_blank" rel="noreferrer"
             className="underline text-red-300">aistudio.google.com/apikey</a>.
        </div>
      )}
      <div className="flex gap-2">
        <input
          value={consulta}
          onChange={(e) => setConsulta(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && enviar()}
          placeholder="¿Qué hago si el CH₄ supera 1.5%? ¿Cuál es el protocolo de evacuación?"
          className="flex-1 bg-gray-900 border border-gray-600 rounded-lg px-3 py-2
                     text-sm text-white placeholder-gray-500 focus:outline-none
                     focus:border-blue-500"
        />
        <button
          onClick={enviar}
          disabled={cargando || !consulta.trim()}
          className="bg-blue-700 hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed
                     px-4 py-2 rounded-lg text-sm font-medium transition-colors"
        >
          {cargando ? "⏳" : "Enviar"}
        </button>
      </div>
      {respuesta && (
        <div className="mt-3 bg-gray-900 rounded-lg p-3 text-sm leading-relaxed whitespace-pre-wrap text-gray-200 border border-gray-600">
          {respuesta.respuesta}
          {respuesta.docs_rag > 0 && (
            <p className="text-xs text-gray-500 mt-2">
              📚 Respaldado por {respuesta.docs_rag} fragmentos normativos (RAG)
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Historial LangGraph por zona ─────────────────────────────────────────────
const DATOS_DEFAULT = {
  zona: "Frente_A_Sogamoso",
  gases:  { CH4: 0.28, CO: 5.8, CO2: 0.11, O2: 20.62, H2S: 0.18 },
  imagen: { deteccion: "normal", confianza: 0.95, n_personas: 2 },
  geo:    { deformacion_mm: 1.5, vibracion_mms: 4.0, presion_kpa: 35,
            convergencia_mm: 2.0, indice_estabilidad: 0.85 },
};

function HistorialLangGraph({ zona }) {
  const [historial,    setHistorial]    = useState(null);
  const [histRegular,  setHistRegular]  = useState([]);
  const [ejecutando,   setEjecutando]   = useState(false);
  const [msgBtn,       setMsgBtn]       = useState("");

  // Carga historial LangGraph (MemorySaver)
  useEffect(() => {
    const cargar = async () => {
      try {
        const r = await fetch(`${ORQUESTADOR}/langgraph/historial/${zona}`);
        if (r.ok) setHistorial(await r.json());
      } catch { /* offline */ }
    };
    cargar();
    const id = setInterval(cargar, 10_000);
    return () => clearInterval(id);
  }, [zona]);

  // Carga historial regular del orquestador como fallback
  useEffect(() => {
    const cargar = async () => {
      try {
        const r = await fetch(`${ORQUESTADOR}/historial?n=10&zona=${zona}`);
        if (r.ok) {
          const d = await r.json();
          setHistRegular(d.eventos || []);
        }
      } catch { /* offline */ }
    };
    cargar();
    const id = setInterval(cargar, 8_000);
    return () => clearInterval(id);
  }, [zona]);

  const ejecutarLangGraph = async () => {
    setEjecutando(true);
    setMsgBtn("Ejecutando ciclo LangGraph…");
    try {
      const payload = { ...DATOS_DEFAULT, zona };
      const r = await fetch(`${ORQUESTADOR}/orquestar_langgraph`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (r.ok) {
        setMsgBtn("Ciclo completado");
        // Refrescar historial
        const rh = await fetch(`${ORQUESTADOR}/langgraph/historial/${zona}`);
        if (rh.ok) setHistorial(await rh.json());
      } else {
        setMsgBtn("Error al ejecutar ciclo");
      }
    } catch {
      setMsgBtn("Orquestador no disponible");
    } finally {
      setEjecutando(false);
      setTimeout(() => setMsgBtn(""), 3000);
    }
  };

  if (!historial) return <p className="text-xs text-gray-500">Cargando historial LangGraph…</p>;

  const niveles = historial.historial_niveles || [];
  const eventos = historial.historial_eventos || [];
  const sinCiclos = (historial.iteracion || 0) === 0;

  // Si no hay ciclos LangGraph, mostrar historial regular como vista previa
  if (sinCiclos) {
    return (
      <div className="space-y-3">
        <div className="bg-gray-800 rounded-lg p-3 border border-indigo-800/40 text-center">
          <p className="text-xs text-gray-400 mb-2">
            El flujo LangGraph aún no se ha ejecutado para esta zona.
          </p>
          <button
            onClick={ejecutarLangGraph}
            disabled={ejecutando}
            className="bg-indigo-700 hover:bg-indigo-600 disabled:opacity-50
                       px-4 py-1.5 rounded-lg text-xs font-medium transition-colors"
          >
            {ejecutando ? "⏳ Ejecutando…" : "▶ Probar ciclo LangGraph"}
          </button>
          {msgBtn && <p className="text-xs text-indigo-300 mt-1">{msgBtn}</p>}
        </div>

        {/* Eventos regulares mientras no hay LangGraph */}
        {histRegular.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 font-medium mb-1">
              Últimos eventos del orquestador (flujo clásico):
            </p>
            <div className="space-y-1 max-h-40 overflow-y-auto">
              {[...histRegular].reverse().map((ev, i) => (
                <div key={i} className="bg-gray-900 rounded p-2 text-xs border border-gray-700">
                  <div className="flex justify-between text-gray-500 mb-0.5">
                    <span>[{ev.id_evento || "—"}]</span>
                    <span>{ev.timestamp?.slice(11, 19)} UTC</span>
                  </div>
                  <span className={`font-semibold ${nivelTextColor(ev.nivel_global)}`}>
                    {ev.nivel_global}
                  </span>
                  {ev.diagnostico_llm && (
                    <p className="text-gray-400 mt-0.5 leading-tight">
                      {ev.diagnostico_llm.slice(0, 100)}…
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  const conteos = niveles.reduce((acc, n) => {
    acc[n] = (acc[n] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs text-gray-400">
          Ciclos completados: <strong className="text-white">{historial.iteracion || 0}</strong>
        </span>
        <div className="flex items-center gap-2">
          {msgBtn && <span className="text-xs text-indigo-300">{msgBtn}</span>}
          <button
            onClick={ejecutarLangGraph}
            disabled={ejecutando}
            className="text-xs bg-indigo-800 hover:bg-indigo-700 disabled:opacity-50
                       px-2 py-1 rounded transition-colors"
          >
            {ejecutando ? "⏳" : "▶ Nuevo ciclo"}
          </button>
          <span className="text-xs text-gray-400">
            Zona: <strong className="text-blue-400">{zona.replace(/_/g, " ")}</strong>
          </span>
        </div>
      </div>

      {/* Distribución de niveles */}
      {Object.keys(conteos).length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500 font-medium">Distribución histórica:</p>
          {Object.entries(conteos).map(([n, c]) => (
            <div key={n} className="flex items-center gap-2 text-xs">
              <span className="w-36 truncate text-gray-300">{n}</span>
              <div className="flex-1 bg-gray-700 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${nivelColor(n)}`}
                  style={{ width: `${Math.min(100, (c / niveles.length) * 100)}%` }}
                />
              </div>
              <span className="text-gray-400 w-8 text-right">{c}×</span>
            </div>
          ))}
        </div>
      )}

      {/* Últimos eventos */}
      {eventos.length > 0 && (
        <div className="mt-2">
          <p className="text-xs text-gray-500 font-medium mb-1">Últimos diagnósticos LLM:</p>
          <div className="max-h-40 overflow-y-auto space-y-1">
            {[...eventos].reverse().slice(0, 5).map((ev, i) => (
              <div key={i} className="bg-gray-900 rounded p-2 text-xs border border-gray-700">
                <div className="flex justify-between text-gray-500 mb-0.5">
                  <span>[{ev.id}]</span>
                  <span>{ev.ts?.slice(11, 19)} UTC</span>
                </div>
                <span className={`font-semibold ${nivelTextColor(ev.nivel)}`}>{ev.nivel}</span>
                {ev.diagnostico_llm && (
                  <p className="text-gray-400 mt-0.5 leading-tight">
                    {ev.diagnostico_llm.slice(0, 120)}…
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {niveles.length === 0 && (
        <p className="text-xs text-gray-500 italic">
          Sin ciclos registrados. Ejecuta una simulación via /orquestar_langgraph.
        </p>
      )}
    </div>
  );
}

// ─── Panel principal ───────────────────────────────────────────────────────────
export function LLMDiagnostico({ ultimoEvento }) {
  const [zonaSeleccionada, setZonaSeleccionada] = useState(ZONAS[0]);

  const ev = ultimoEvento;
  const tieneLLM = ev?.diagnostico_llm || ev?.pronostico_llm;

  return (
    <div className="space-y-4">

      {/* Último diagnóstico LLM del evento WebSocket */}
      {tieneLLM ? (
        <div className="bg-gray-900 rounded-xl p-4 border border-indigo-800">
          <div className="flex justify-between items-start mb-3">
            <h2 className="font-bold text-lg">🧠 Diagnóstico LLM (Tiempo Real)</h2>
            <span className="text-xs px-2 py-1 rounded bg-indigo-800 text-indigo-200">
              {ev.motor === "LangGraph" ? "⚡ LangGraph" : "Orquestador"}
            </span>
          </div>

          {ev.diagnostico_llm && (
            <div className="mb-3 p-3 bg-gray-800 rounded-lg border border-gray-700">
              <p className="text-xs text-gray-400 font-medium mb-1">📋 Diagnóstico:</p>
              <p className="text-sm text-gray-100 leading-relaxed">{ev.diagnostico_llm}</p>
            </div>
          )}

          {ev.acciones_llm?.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-gray-400 font-medium mb-1">⚡ Acciones recomendadas:</p>
              {ev.acciones_llm.map((a, i) => (
                <div key={i} className="flex gap-2 text-sm py-0.5">
                  <span className="text-blue-400 font-bold">{i + 1}.</span>
                  <span className="text-gray-200">{a}</span>
                </div>
              ))}
            </div>
          )}

          {ev.referencia_llm && (
            <div className="mb-3 p-2 bg-blue-950 rounded border border-blue-800">
              <p className="text-xs text-blue-300">
                📖 <strong>Referencia normativa:</strong> {ev.referencia_llm}
              </p>
            </div>
          )}

          {ev.pronostico_llm && (
            <div className="p-2 bg-orange-950 rounded border border-orange-800">
              <p className="text-xs text-orange-300">
                🔮 <strong>Pronóstico:</strong> {ev.pronostico_llm}
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
          <h2 className="font-bold text-lg mb-2">🧠 Diagnóstico LLM</h2>
          <p className="text-sm text-gray-400">
            Sin datos LLM todavía. Activa la simulación y usa{" "}
            <code className="bg-gray-800 px-1 rounded text-blue-300">/orquestar_langgraph</code>{" "}
            para ver diagnósticos en tiempo real.
          </p>
        </div>
      )}

      {/* Historial LangGraph */}
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
        <div className="flex justify-between items-center mb-3">
          <h3 className="font-bold text-sm">📈 Historial LangGraph (Memoria Cíclica)</h3>
          <select
            value={zonaSeleccionada}
            onChange={(e) => setZonaSeleccionada(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-white
                       focus:outline-none focus:border-blue-500"
          >
            {ZONAS.map((z) => (
              <option key={z} value={z}>{z.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>
        <HistorialLangGraph zona={zonaSeleccionada} />
      </div>
    </div>
  );
}

// ─── Helpers de color ─────────────────────────────────────────────────────────
function nivelColor(nivel) {
  if (nivel.includes("EVACUACIÓN")) return "bg-purple-500";
  if (nivel.includes("EMERGENCIA")) return "bg-red-500";
  if (nivel.includes("ALTO"))       return "bg-orange-500";
  if (nivel.includes("PRECAUCIÓN")) return "bg-yellow-500";
  return "bg-green-500";
}

function nivelTextColor(nivel) {
  if (nivel.includes("EVACUACIÓN")) return "text-purple-400";
  if (nivel.includes("EMERGENCIA")) return "text-red-400";
  if (nivel.includes("ALTO"))       return "text-orange-400";
  if (nivel.includes("PRECAUCIÓN")) return "text-yellow-400";
  return "text-green-400";
}
