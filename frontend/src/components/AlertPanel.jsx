/**
 * AlertPanel.jsx — Panel de alertas activas con causa detallada y normativa.
 */

import React, { useState } from "react";

const ESTILOS_NIVEL = {
  "EVACUACIÓN INMEDIATA": "border-purple-500 bg-purple-950 text-purple-200",
  "EMERGENCIA":           "border-red-600   bg-red-950   text-red-200",
  "RIESGO ALTO":          "border-orange-500 bg-orange-950 text-orange-100",
  "PRECAUCIÓN":           "border-yellow-400 bg-yellow-900 text-yellow-100",
  "INFORMATIVO":          "border-blue-400  bg-blue-900  text-blue-100",
  "SEGURO":               "border-green-500 bg-green-950 text-green-200",
};

const ICONOS_NIVEL = {
  "EVACUACIÓN INMEDIATA": "🚨", "EMERGENCIA": "🔴",
  "RIESGO ALTO": "⚠️", "PRECAUCIÓN": "🟡",
  "INFORMATIVO": "ℹ️", "SEGURO": "✅",
};

const COLOR_NIVEL = {
  "EVACUACIÓN INMEDIATA": "text-purple-300",
  "EMERGENCIA":           "text-red-300",
  "RIESGO ALTO":          "text-orange-300",
  "PRECAUCIÓN":           "text-yellow-300",
};

// ─── Umbrales frontend (Decreto 1886/2015) — espejo del backend ───────────────
const LIMITES = {
  CH4:  { nombre: "Metano (CH₄)",          unidad: "%",   norma: "Art. 120 D.1886",
    fn: v => v >= 5.0 ? "EVACUACIÓN INMEDIATA" : v >= 1.5 ? "RIESGO ALTO" : v >= 0.5 ? "PRECAUCIÓN" : "SEGURO" },
  CO:   { nombre: "Monóxido de Carbono (CO)", unidad: "ppm", norma: "Art. 123 D.1886",
    fn: v => v >= 200 ? "EVACUACIÓN INMEDIATA" : v >= 50 ? "RIESGO ALTO" : v >= 25 ? "PRECAUCIÓN" : "SEGURO" },
  CO2:  { nombre: "Dióxido de Carbono (CO₂)", unidad: "%",  norma: "Art. 119 D.1886",
    fn: v => v >= 3.0 ? "EVACUACIÓN INMEDIATA" : v >= 1.5 ? "RIESGO ALTO" : v >= 0.5 ? "PRECAUCIÓN" : "SEGURO" },
  O2:   { nombre: "Oxígeno (O₂)",            unidad: "%",   norma: "Art. 118 D.1886",
    fn: v => v < 16.0 ? "EVACUACIÓN INMEDIATA" : v < 17.5 ? "RIESGO ALTO" : v < 19.5 ? "PRECAUCIÓN" : "SEGURO" },
  H2S:  { nombre: "Sulfuro de Hidrógeno (H₂S)", unidad: "ppm", norma: "OSHA PEL / Art. 69",
    fn: v => v >= 50 ? "EVACUACIÓN INMEDIATA" : v >= 10 ? "RIESGO ALTO" : v >= 1.0 ? "PRECAUCIÓN" : "SEGURO" },
};

// Calcula gases fuera de rango a partir de las lecturas crudas del evento
function calcularGasesAlerta(datosGases) {
  if (!datosGases || typeof datosGases !== "object") return [];
  return Object.entries(datosGases)
    .map(([gas, valor]) => {
      const def = LIMITES[gas];
      if (!def || typeof valor !== "number") return null;
      const nivel = def.fn(valor);
      if (nivel === "SEGURO") return null;
      return { gas, nombre: def.nombre, unidad: def.unidad, norma: def.norma, valor, nivel };
    })
    .filter(Boolean)
    .sort((a, b) => {
      const ord = { "PRECAUCIÓN": 1, "RIESGO ALTO": 2, "EMERGENCIA": 3, "EVACUACIÓN INMEDIATA": 4 };
      return (ord[b.nivel] || 0) - (ord[a.nivel] || 0);
    });
}

// ─── Sección de label pequeño ──────────────────────────────────────────────────
function Label({ children }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-wider opacity-50 mt-2.5 mb-0.5">
      {children}
    </p>
  );
}

// ─── Razón principal de la alerta ──────────────────────────────────────────────
function FilaGas({ g }) {
  return (
    <div className="flex items-start gap-1.5 mt-1">
      <span className="text-xs shrink-0 mt-0.5">•</span>
      <span className="text-xs leading-snug">
        <span className="font-semibold">{g.nombre ?? g.gas}</span>
        {": "}
        <span className={`font-bold ${COLOR_NIVEL[g.nivel] || "text-white"}`}>
          {typeof g.valor === "number" ? g.valor.toFixed(3) : g.valor} {g.unidad}
        </span>
        <span className="opacity-60 ml-1">— {g.nivel}</span>
        {g.norma && <span className="text-gray-400 ml-1">({g.norma})</span>}
      </span>
    </div>
  );
}

function RazonPrincipal({ evento }) {
  const correlaciones = evento.correlaciones || [];

  // gases_criticos viene del backend; si está vacío lo calculamos del frontend
  const gasesBackend  = evento.gases_criticos || [];
  const gasesCalc     = calcularGasesAlerta(evento.datos_gases);
  const gases         = gasesBackend.length > 0 ? gasesBackend : gasesCalc;

  // ── 1. Correlaciones multiagente (causa más grave) ─────────────────────────
  if (correlaciones.length > 0) {
    return (
      <div className="mt-2 bg-black/20 rounded-lg p-2 border border-white/10">
        <Label>⚡ Por qué se activó</Label>
        {correlaciones.map((c, i) => (
          <div key={i} className="flex items-start gap-1.5 mt-1">
            <span className="text-orange-300 text-xs shrink-0 mt-0.5">▸</span>
            <span className="text-xs font-semibold leading-tight text-orange-100">{c}</span>
          </div>
        ))}
        {gases.length > 0 && (
          <>
            <Label>📊 Parámetros que lo provocaron</Label>
            {gases.map((g, i) => <FilaGas key={i} g={g} />)}
          </>
        )}
      </div>
    );
  }

  // ── 2. Gases fuera de umbral (causa directa) ───────────────────────────────
  if (gases.length > 0) {
    return (
      <div className="mt-2 bg-black/20 rounded-lg p-2 border border-white/10">
        <Label>📊 Por qué se activó</Label>
        {gases.map((g, i) => <FilaGas key={i} g={g} />)}
      </div>
    );
  }

  // ── 3. Fallback: estado por agente (extraído del campo explicacion) ─────────
  const expl = evento.explicacion || "";
  // Buscar líneas del bloque "ESTADO POR AGENTE:" que tengan nivel no-seguro
  const lineasAgente = expl
    .split("\n")
    .filter(l => l.includes("[") && l.includes("]") && !l.includes("OFFLINE") && !l.includes("SEGURO"))
    .slice(0, 3);

  if (lineasAgente.length > 0) {
    return (
      <div className="mt-2 bg-black/20 rounded-lg p-2 border border-white/10">
        <Label>📋 Estado de agentes que lo activaron</Label>
        {lineasAgente.map((l, i) => (
          <p key={i} className="text-xs opacity-80 leading-snug font-mono">{l.trim()}</p>
        ))}
      </div>
    );
  }

  return null;
}

// ─── Diagnóstico LLM expandible ────────────────────────────────────────────────
function DiagnosticoLLM({ diagnostico, referencia, pronostico }) {
  const [abierto, setAbierto] = useState(false);
  if (!diagnostico) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setAbierto(a => !a)}
        className="flex items-center gap-1 text-[10px] uppercase tracking-wider
                   opacity-50 hover:opacity-80 transition-opacity w-full text-left"
      >
        🧠 Diagnóstico LLM {abierto ? "▴" : "▾"}
      </button>
      {abierto && (
        <div className="mt-1 bg-indigo-950/60 rounded p-2 border border-indigo-800/40">
          <p className="text-xs leading-snug text-indigo-100">{diagnostico}</p>
          {referencia && (
            <p className="text-[10px] text-indigo-400 mt-1">
              📖 {referencia}
            </p>
          )}
          {pronostico && (
            <p className="text-[10px] text-orange-300 mt-1">
              🔮 {pronostico}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Normativa incumplida ──────────────────────────────────────────────────────
function Normativa({ gasesCliticos, normativaRag }) {
  const normasGas = [...new Set(
    (gasesCliticos || []).map(g => g.norma || g.articulo).filter(Boolean)
  )];
  const normasRag = (normativaRag || []).filter(
    n => !normasGas.some(ng => ng.includes(n) || n.includes(ng))
  );
  const todas = [...normasGas, ...normasRag].slice(0, 5);
  if (todas.length === 0) return null;

  return (
    <>
      <Label>📋 Normativa incumplida</Label>
      {normasGas.map((n, i) => (
        <p key={`g${i}`} className="text-xs mb-0.5 font-medium">⚖ {n}</p>
      ))}
      {normasRag.map((n, i) => (
        <p key={`r${i}`} className="text-xs mb-0.5 opacity-80">📄 {n}</p>
      ))}
    </>
  );
}

// ─── Acciones inmediatas ───────────────────────────────────────────────────────
function Acciones({ acciones }) {
  if (!acciones?.length) return null;
  return (
    <>
      <Label>🛡 Acciones inmediatas</Label>
      {acciones.slice(0, 3).map((a, i) => (
        <p key={i} className="text-xs mt-0.5">• {a}</p>
      ))}
    </>
  );
}

// ─── Tarjeta de alerta ─────────────────────────────────────────────────────────
function TarjetaAlerta({ ev }) {
  const [expandido, setExpandido] = useState(false);

  return (
    <div className={`border rounded-lg p-3 ${ESTILOS_NIVEL[ev.nivel_global] || "border-gray-600 bg-gray-800"}`}>

      {/* Cabecera */}
      <div className="flex justify-between items-start">
        <span className="font-bold text-sm">
          {ICONOS_NIVEL[ev.nivel_global]} {ev.nivel_global}
        </span>
        <div className="text-right">
          <p className="text-[10px] opacity-60">{ev.timestamp?.slice(0, 19)?.replace("T", " ")}</p>
          <p className="text-xs font-medium mt-0.5">{ev.zona?.replace(/_/g, " ")}</p>
        </div>
      </div>

      {/* Razón principal — siempre visible */}
      <RazonPrincipal evento={ev} />

      {/* Normativa + acciones + LLM — colapsables */}
      {expandido && (
        <div className="mt-1">
          <Normativa gasesCliticos={ev.gases_criticos} normativaRag={ev.normativa} />
          <Acciones acciones={ev.acciones_globales} />
          <DiagnosticoLLM
            diagnostico={ev.diagnostico_llm}
            referencia={ev.referencia_llm}
            pronostico={ev.pronostico_llm}
          />
          {ev.prediccion && (
            <p className="text-xs mt-2 opacity-70 italic">{ev.prediccion}</p>
          )}
        </div>
      )}

      {/* Toggle expandir */}
      <button
        onClick={() => setExpandido(e => !e)}
        className="mt-2 text-[10px] uppercase tracking-wide opacity-40 hover:opacity-70
                   transition-opacity w-full text-left"
      >
        {expandido ? "▴ Mostrar menos" : "▾ Ver normativa y acciones"}
      </button>
    </div>
  );
}

// ─── Panel principal ───────────────────────────────────────────────────────────
export function AlertPanel({ eventos }) {
  const criticos = eventos
    .filter(e =>
      ["EVACUACIÓN INMEDIATA", "EMERGENCIA", "RIESGO ALTO", "PRECAUCIÓN"].includes(e.nivel_global)
    )
    .slice(0, 20);

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700 flex flex-col h-full">
      <div className="flex justify-between items-center mb-3 flex-shrink-0">
        <h2 className="text-white font-bold text-lg">
          🚨 Alertas Activas ({criticos.length})
        </h2>
        {criticos.length > 0 && (
          <span className="text-xs text-gray-500">Más reciente primero</span>
        )}
      </div>

      {criticos.length === 0 ? (
        <p className="text-green-400 text-sm">✅ Sin alertas activas</p>
      ) : (
        <div className="space-y-3 overflow-y-auto flex-1 pr-1
                        scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent">
          {criticos.map((ev, i) => (
            <TarjetaAlerta key={ev.id_evento || i} ev={ev} />
          ))}
        </div>
      )}
    </div>
  );
}
