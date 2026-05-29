/**
 * AlertPanel.jsx — Panel de alertas activas con causa normativa y nivel de riesgo.
 */

import React from "react";

const ESTILOS_NIVEL = {
  "EVACUACIÓN INMEDIATA": "border-purple-500 bg-purple-950 text-purple-200",
  "EMERGENCIA":           "border-red-600   bg-red-950   text-red-200",
  "RIESGO ALTO":          "border-red-400   bg-red-900   text-red-100",
  "PRECAUCIÓN":           "border-yellow-400 bg-yellow-900 text-yellow-100",
  "INFORMATIVO":          "border-blue-400  bg-blue-900  text-blue-100",
  "SEGURO":               "border-green-500 bg-green-950 text-green-200",
};

const ICONOS_NIVEL = {
  "EVACUACIÓN INMEDIATA": "🚨", "EMERGENCIA": "🔴",
  "RIESGO ALTO": "⚠️", "PRECAUCIÓN": "🟡",
  "INFORMATIVO": "ℹ️", "SEGURO": "✅",
};

function SeccionLabel({ children }) {
  return (
    <p className="text-xs font-bold uppercase tracking-wide opacity-50 mt-2 mb-0.5">
      {children}
    </p>
  );
}

function NormativaIncumplida({ gasesCliticos, normativaRag }) {
  // Artículos por gas (del agente de gases, siempre presentes)
  const normasGas = [...new Set(
    (gasesCliticos || [])
      .map((g) => g.norma || g.articulo)
      .filter(Boolean)
  )];

  // Títulos del corpus RAG (pueden ser vacíos si el índice FAISS no cargó)
  const normasRag = (normativaRag || []).filter(
    (n) => !normasGas.some((ng) => ng.includes(n) || n.includes(ng))
  );

  const todas = [...normasGas, ...normasRag].slice(0, 5);

  if (todas.length === 0) return null;

  return (
    <div className="mt-1 pt-2 border-t border-white/10">
      <SeccionLabel>📋 Normativa incumplida</SeccionLabel>
      {normasGas.map((n, i) => (
        <p key={`gas-${i}`} className="text-xs mb-0.5 font-medium">
          ⚖ {n}
        </p>
      ))}
      {normasRag.map((n, i) => (
        <p key={`rag-${i}`} className="text-xs mb-0.5 opacity-80">
          📄 {n}
        </p>
      ))}
    </div>
  );
}

function CausaActivacion({ correlaciones, gasesCliticos, explicacion }) {
  const tieneCausa = correlaciones?.length > 0 || gasesCliticos?.length > 0;

  return (
    <div className="mt-1 pt-2 border-t border-white/10">
      <SeccionLabel>⚠ Causa de activación</SeccionLabel>

      {/* Reglas de correlación multiagente disparadas */}
      {correlaciones?.map((c, i) => (
        <p key={i} className="text-xs mb-0.5 font-semibold">
          ⚡ {c}
        </p>
      ))}

      {/* Gases fuera de rango con sus valores */}
      {gasesCliticos?.length > 0 && (
        <div className={correlaciones?.length > 0 ? "mt-1" : ""}>
          {gasesCliticos.map((g, i) => (
            <p key={i} className="text-xs mb-0.5">
              •{" "}
              <span className="font-medium">{g.nombre ?? g.gas}</span>:{" "}
              {typeof g.valor === "number" ? g.valor.toFixed(3) : g.valor}{" "}
              {g.unidad} —{" "}
              <span className="font-semibold">{g.nivel}</span>
            </p>
          ))}
        </div>
      )}

      {/* Fallback si no hay datos estructurados */}
      {!tieneCausa && explicacion && (
        <p className="text-xs opacity-70 italic">
          {explicacion.split("\n").find((l) => l.includes("Gases críticos")) ||
            explicacion.slice(0, 120)}
        </p>
      )}
    </div>
  );
}

export function AlertPanel({ eventos }) {
  const criticos = eventos
    .filter((e) =>
      ["EVACUACIÓN INMEDIATA", "EMERGENCIA", "RIESGO ALTO"].includes(e.nivel_global)
    )
    .slice(0, 10);

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
      <h2 className="text-white font-bold text-lg mb-3">
        🚨 Alertas Activas ({criticos.length})
      </h2>

      {criticos.length === 0 ? (
        <p className="text-green-400 text-sm">✅ Sin alertas críticas activas</p>
      ) : (
        <div className="space-y-3 max-h-[36rem] overflow-y-auto pr-1">
          {criticos.map((ev, i) => (
            <div
              key={i}
              className={`border rounded-lg p-3 ${ESTILOS_NIVEL[ev.nivel_global]}`}
            >
              {/* Encabezado: nivel + timestamp */}
              <div className="flex justify-between items-start">
                <span className="font-bold">
                  {ICONOS_NIVEL[ev.nivel_global]} {ev.nivel_global}
                </span>
                <span className="text-xs opacity-70">
                  {ev.timestamp?.slice(0, 19)}
                </span>
              </div>

              {/* Zona */}
              <p className="text-sm mt-1 font-medium">
                {ev.zona?.replace(/_/g, " ")}
              </p>

              {/* Causa de activación */}
              <CausaActivacion
                correlaciones={ev.correlaciones}
                gasesCliticos={ev.gases_criticos}
                explicacion={ev.explicacion}
              />

              {/* Normativa incumplida */}
              <NormativaIncumplida
                gasesCliticos={ev.gases_criticos}
                normativaRag={ev.normativa}
              />

              {/* Acciones recomendadas */}
              {ev.acciones_globales?.length > 0 && (
                <div className="mt-1 pt-2 border-t border-white/10">
                  <SeccionLabel>🛡 Acciones inmediatas</SeccionLabel>
                  {ev.acciones_globales.slice(0, 2).map((a, j) => (
                    <p key={j} className="text-xs mt-0.5">
                      • {a}
                    </p>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
