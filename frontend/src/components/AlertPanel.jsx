/**
 * AlertPanel.jsx — Panel de alertas activas con priorización visual.
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

export function AlertPanel({ eventos }) {
  const criticos = eventos.filter(
    (e) => ["EVACUACIÓN INMEDIATA","EMERGENCIA","RIESGO ALTO"].includes(e.nivel_global)
  ).slice(0, 10);

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
      <h2 className="text-white font-bold text-lg mb-3">
        🚨 Alertas Activas ({criticos.length})
      </h2>
      {criticos.length === 0 ? (
        <p className="text-green-400 text-sm">✅ Sin alertas críticas activas</p>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {criticos.map((ev, i) => (
            <div key={i}
              className={`border rounded-lg p-3 ${ESTILOS_NIVEL[ev.nivel_global]}`}>
              <div className="flex justify-between items-start">
                <span className="font-bold">
                  {ICONOS_NIVEL[ev.nivel_global]} {ev.nivel_global}
                </span>
                <span className="text-xs opacity-70">
                  {ev.timestamp?.slice(0,19)}
                </span>
              </div>
              <p className="text-sm mt-1 font-medium">{ev.zona?.replace(/_/g," ")}</p>
              {ev.correlaciones?.length > 0 && (
                <p className="text-xs mt-1 opacity-80">
                  ⚡ {ev.correlaciones[0]}
                </p>
              )}
              {ev.acciones_globales?.slice(0,2).map((a, j) => (
                <p key={j} className="text-xs mt-1">• {a}</p>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}