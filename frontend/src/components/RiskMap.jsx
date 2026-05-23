/**
 * RiskMap.jsx — Mapa visual de riesgo por zona de la mina.
 */

import React from "react";

const ZONAS_CONFIG = {
  Frente_A_Sogamoso: { x: 20,  y: 30, label: "Frente A\nSogamoso" },
  Frente_B_Mongua:   { x: 55,  y: 30, label: "Frente B\nMongua"   },
  Galeria_Central:   { x: 37,  y: 55, label: "Galería\nCentral"   },
  Bocamina:          { x: 37,  y: 75, label: "Bocamina"           },
};

const COLORES_NIVEL = {
  SEGURO:                  "#2ecc71",
  INFORMATIVO:             "#3498db",
  "PRECAUCIÓN":            "#f39c12",
  "RIESGO ALTO":           "#e74c3c",
  EMERGENCIA:              "#c0392b",
  "EVACUACIÓN INMEDIATA":  "#8e44ad",
};

export function RiskMap({ eventos }) {
  // Construir mapa zona → último nivel
  const nivelPorZona = {};
  for (const ev of eventos) {
    if (!nivelPorZona[ev.zona]) {
      nivelPorZona[ev.zona] = ev.nivel_global;
    }
  }

  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
      <h2 className="text-white font-bold text-lg mb-3">🗺️ Mapa de Riesgo — Mina</h2>
      <svg viewBox="0 0 100 100" className="w-full h-64">
        {/* Galería principal */}
        <line x1="37" y1="30" x2="37" y2="75" stroke="#555" strokeWidth="2"/>
        <line x1="20" y1="30" x2="55" y2="30" stroke="#555" strokeWidth="2"/>

        {Object.entries(ZONAS_CONFIG).map(([zona, cfg]) => {
          const nivel  = nivelPorZona[zona] || "SEGURO";
          const color  = COLORES_NIVEL[nivel] || "#2ecc71";
          const parpadear = ["EMERGENCIA","EVACUACIÓN INMEDIATA"].includes(nivel);
          return (
            <g key={zona}>
              <circle
                cx={cfg.x} cy={cfg.y} r="7"
                fill={color}
                opacity={parpadear ? undefined : 0.9}
                className={parpadear ? "animate-pulse" : ""}
              />
              <text x={cfg.x} y={cfg.y + 12} textAnchor="middle"
                    fontSize="4" fill="#ccc">{zona.replace(/_/g," ")}</text>
            </g>
          );
        })}
      </svg>

      {/* Leyenda */}
      <div className="flex flex-wrap gap-2 mt-2">
        {Object.entries(COLORES_NIVEL).map(([nivel, color]) => (
          <span key={nivel} className="flex items-center gap-1 text-xs text-gray-300">
            <span className="w-3 h-3 rounded-full inline-block" style={{background: color}}/>
            {nivel}
          </span>
        ))}
      </div>
    </div>
  );
}