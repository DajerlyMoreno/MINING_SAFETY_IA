/**
 * RiskMap.jsx — Mapa visual de riesgo por zona de la mina.
 *
 * Comportamiento de seguridad en tiempo real (doble fuente):
 *  • Gas Agent polling cada 5 s  → clasificación local inmediata (piso de seguridad)
 *  • Orquestador WebSocket       → nivel oficial; prevalece si es >= al local
 *
 * Regla: se muestra el nivel MÁS ALTO entre ambas fuentes.
 * Esto garantiza que un pico de gas aparezca en el mapa de inmediato,
 * sin esperar el ciclo completo del orquestador.
 */

import React, { useState, useEffect, useRef } from "react";

const AGENTE_GAS = import.meta.env.VITE_AGENTE_GAS || "http://localhost:8001";

const ZONAS = [
  "Frente_A_Sogamoso",
  "Frente_B_Mongua",
  "Galeria_Central",
  "Bocamina",
];

const ZONAS_CONFIG = {
  Frente_A_Sogamoso: { x: 22,  y: 22, label: ["Frente A", "Sogamoso"] },
  Frente_B_Mongua:   { x: 68,  y: 22, label: ["Frente B", "Mongua"]   },
  Galeria_Central:   { x: 45,  y: 52, label: ["Galería",  "Central"]  },
  Bocamina:          { x: 45,  y: 78, label: ["Bocamina"]             },
};

const COLORES_NIVEL = {
  "SEGURO":                 "#2ecc71",
  "INFORMATIVO":            "#3498db",
  "PRECAUCIÓN":             "#f39c12",
  "RIESGO ALTO":            "#e74c3c",
  "EMERGENCIA":             "#c0392b",
  "EVACUACIÓN INMEDIATA":   "#8e44ad",
};

const NIVEL_ORDEN = {
  "SEGURO": 0, "INFORMATIVO": 1, "PRECAUCIÓN": 2,
  "RIESGO ALTO": 3, "EMERGENCIA": 4, "EVACUACIÓN INMEDIATA": 5,
};

// Umbrales Decreto 1886/2015 (mismos que GasPanel)
const UMBRALES = {
  CH4:  [[0.5,"SEGURO"],[1.0,"INFORMATIVO"],[1.5,"PRECAUCIÓN"],[2.5,"RIESGO ALTO"],[5.0,"EMERGENCIA"],[Infinity,"EVACUACIÓN INMEDIATA"]],
  CO:   [[10,"SEGURO"],[25,"INFORMATIVO"],[50,"PRECAUCIÓN"],[100,"RIESGO ALTO"],[200,"EMERGENCIA"],[Infinity,"EVACUACIÓN INMEDIATA"]],
  CO2:  [[0.5,"SEGURO"],[1.0,"INFORMATIVO"],[1.5,"PRECAUCIÓN"],[3.0,"RIESGO ALTO"],[5.0,"EMERGENCIA"],[Infinity,"EVACUACIÓN INMEDIATA"]],
  H2S:  [[1,"SEGURO"],[5,"INFORMATIVO"],[10,"PRECAUCIÓN"],[20,"RIESGO ALTO"],[50,"EMERGENCIA"],[Infinity,"EVACUACIÓN INMEDIATA"]],
};

function clasificarGas(gas, valor) {
  if (gas === "O2") {
    if (valor >= 19.5) return "SEGURO";
    if (valor >= 18.0) return "PRECAUCIÓN";
    if (valor >= 16.0) return "RIESGO ALTO";
    return "EMERGENCIA";
  }
  const umb = UMBRALES[gas] || [];
  for (const [max, nivel] of umb) if (valor < max) return nivel;
  return "SEGURO";
}

function clasificarGases(gases) {
  let max = "SEGURO";
  for (const [gas, val] of Object.entries(gases)) {
    const n = clasificarGas(gas, val);
    if ((NIVEL_ORDEN[n] ?? 0) > (NIVEL_ORDEN[max] ?? 0)) max = n;
  }
  return max;
}

function nivelMasAlto(a, b) {
  return (NIVEL_ORDEN[a] ?? 0) >= (NIVEL_ORDEN[b] ?? 0) ? a : b;
}

function normalizarNivel(nivel) {
  if (!nivel) return "SEGURO";
  const n = nivel.toUpperCase().trim();
  if (n.includes("EVACUACI")) return "EVACUACIÓN INMEDIATA";
  if (n.includes("EMERGENCIA"))  return "EMERGENCIA";
  if (n.includes("RIESGO"))      return "RIESGO ALTO";
  if (n.includes("PRECAU"))      return "PRECAUCIÓN";
  if (n.includes("INFORMAT"))    return "INFORMATIVO";
  return "SEGURO";
}

// ── Componente ────────────────────────────────────────────────────────────────
export function RiskMap({ eventos = [] }) {
  // Nivel local (gas agent polling — reacciona en ~5 s)
  const [nivelLocal,  setNivelLocal]  = useState({});
  // Nivel orquestador (WebSocket — decisión oficial)
  const [nivelOrq,    setNivelOrq]    = useState({});
  // Gases crudos para tooltip
  const [gasesPorZona, setGasesPorZona] = useState({});

  const [hoveredZona,  setHoveredZona]  = useState(null);
  const [tooltipPos,   setTooltipPos]   = useState({ x: 0, y: 0 });
  const timerRef = useRef(null);

  // ── Polling Gas Agent cada 5 s (reacción rápida) ─────────────────────────
  const fetchZona = async (zona) => {
    try {
      const res = await fetch(`${AGENTE_GAS}/historial/${zona}?n=1`);
      if (!res.ok) return;
      const data = await res.json();
      const lecturas = data.lecturas || [];
      if (!lecturas.length) return;
      const gases = lecturas[lecturas.length - 1];
      const nivel = clasificarGases(gases);
      setGasesPorZona(prev => ({ ...prev, [zona]: gases }));
      setNivelLocal(prev => ({ ...prev, [zona]: nivel }));
    } catch { /* agente offline */ }
  };

  useEffect(() => {
    ZONAS.forEach(fetchZona);
    timerRef.current = setInterval(() => ZONAS.forEach(fetchZona), 5000);
    return () => clearInterval(timerRef.current);
  }, []);

  // ── Orquestador WebSocket (decisión oficial) ──────────────────────────────
  useEffect(() => {
    if (!eventos || eventos.length === 0) return;
    const updates = {};
    for (const ev of eventos) {               // eventos[0] = más reciente
      if (!ev.zona) continue;
      if (updates[ev.zona] === undefined)
        updates[ev.zona] = normalizarNivel(ev.nivel_global);
    }
    setNivelOrq(prev => ({ ...prev, ...updates }));
  }, [eventos]);

  // ── Nivel efectivo = máximo entre local y orquestador ────────────────────
  const nivelEfectivo = (zona) => {
    const local = nivelLocal[zona] || "SEGURO";
    const orq   = nivelOrq[zona]   || "SEGURO";
    return nivelMasAlto(local, orq);
  };

  const fuenteLabel = (zona) => {
    const local = NIVEL_ORDEN[nivelLocal[zona]] ?? 0;
    const orq   = NIVEL_ORDEN[nivelOrq[zona]]   ?? 0;
    if (!nivelOrq[zona] && !nivelLocal[zona]) return null;
    if (orq > local) return "orquestador";
    if (local > 0)   return "sensor";
    return null;
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700 relative">
      <div className="flex justify-between items-center mb-3">
        <h2 className="text-white font-bold text-lg">🗺️ Mapa de Riesgo — Mina</h2>
        <span className="text-xs text-gray-500">Sensor ~5 s · Orquestador en vivo</span>
      </div>

      <svg
        viewBox="0 0 120 100"
        className="w-full h-72"
        style={{ background: "linear-gradient(180deg,#1a1a2e 0%,#16213e 100%)", borderRadius: 8 }}
      >
        <line x1="22" y1="22" x2="45" y2="52" stroke="#4a5568" strokeWidth="2.5" strokeLinecap="round"/>
        <line x1="68" y1="22" x2="45" y2="52" stroke="#4a5568" strokeWidth="2.5" strokeLinecap="round"/>
        <line x1="45" y1="52" x2="45" y2="78" stroke="#4a5568" strokeWidth="2.5" strokeLinecap="round"/>
        <text x="60" y="38" fontSize="3.5" fill="#4a5568" textAnchor="middle">Galería Principal</text>

        {Object.entries(ZONAS_CONFIG).map(([zona, cfg]) => {
          const nivel  = nivelEfectivo(zona);
          const color  = COLORES_NIVEL[nivel] || "#2ecc71";
          const pulsar = ["EMERGENCIA", "EVACUACIÓN INMEDIATA"].includes(nivel);
          const hayDatos = !!(nivelLocal[zona] || nivelOrq[zona]);

          return (
            <g key={zona}
              onMouseEnter={(e) => {
                setHoveredZona(zona);
                const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect();
                setTooltipPos({
                  x: (cfg.x / 120) * rect.width + rect.left,
                  y: (cfg.y / 100) * rect.height + rect.top,
                });
              }}
              onMouseLeave={() => setHoveredZona(null)}
              style={{ cursor: "pointer" }}
            >
              <circle cx={cfg.x} cy={cfg.y} r="10" fill={color} opacity="0.15"
                className={pulsar ? "animate-pulse" : ""}/>
              <circle cx={cfg.x} cy={cfg.y} r="7" fill={color}
                opacity={hayDatos ? 0.9 : 0.35}
                stroke={pulsar ? "#fff" : color}
                strokeWidth={pulsar ? "0.8" : "0"}
                className={pulsar ? "animate-pulse" : ""}/>
              {cfg.label.map((linea, i) => (
                <text key={i} x={cfg.x} y={cfg.y + 12 + i * 4.5}
                  textAnchor="middle" fontSize="3.8" fill="#d1d5db" fontWeight="500">
                  {linea}
                </text>
              ))}
              {nivel !== "SEGURO" && (
                <text x={cfg.x} y={cfg.y - 9} textAnchor="middle"
                  fontSize="3" fill={color} fontWeight="bold">
                  {nivel}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hoveredZona && (
        <div className="fixed z-50 bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-xl pointer-events-none"
          style={{ left: tooltipPos.x + 16, top: tooltipPos.y - 60, minWidth: 200 }}>
          <p className="text-white font-bold text-xs mb-1">{hoveredZona.replace(/_/g," ")}</p>
          <p className="text-xs mb-1" style={{ color: COLORES_NIVEL[nivelEfectivo(hoveredZona)] }}>
            ● {nivelEfectivo(hoveredZona)}
          </p>
          {fuenteLabel(hoveredZona) && (
            <p className="text-xs text-gray-500 mb-2">
              fuente: {fuenteLabel(hoveredZona) === "orquestador"
                ? "🧠 orquestador" : "📡 lectura directa"}
            </p>
          )}
          {gasesPorZona[hoveredZona] ? (
            <table className="text-xs w-full">
              <tbody>
                {["CH4","CO","CO2","O2","H2S"].map(gas => {
                  const val = gasesPorZona[hoveredZona][gas];
                  if (val === undefined) return null;
                  const nGas  = clasificarGas(gas, val);
                  const color = COLORES_NIVEL[nGas] || "#9ca3af";
                  const unidad = ["O2","CH4","CO2"].includes(gas) ? "%" : "ppm";
                  return (
                    <tr key={gas}>
                      <td className="text-gray-400 pr-2">{gas}</td>
                      <td className="font-mono" style={{ color }}>{Number(val).toFixed(3)}</td>
                      <td className="text-gray-500 pl-1">{unidad}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="text-gray-500 text-xs">Cargando lecturas…</p>
          )}
        </div>
      )}

      {/* Leyenda */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3">
        {Object.entries(COLORES_NIVEL).map(([nivel, color]) => (
          <span key={nivel} className="flex items-center gap-1 text-xs text-gray-300">
            <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: color }}/>
            {nivel}
          </span>
        ))}
      </div>

      {/* Grid de estado por zona */}
      <div className="mt-3 grid grid-cols-2 gap-1">
        {ZONAS.map(zona => {
          const nivel = nivelEfectivo(zona);
          const color = COLORES_NIVEL[nivel] || "#6b7280";
          const fuente = fuenteLabel(zona);
          return (
            <div key={zona} className="flex items-center gap-2 bg-gray-800 rounded px-2 py-1">
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }}/>
              <span className="text-xs text-gray-300 truncate">{zona.replace(/_/g," ")}</span>
              <span className="text-xs font-medium ml-auto" style={{ color }}>{nivel}</span>
              {fuente === "sensor" && <span className="text-xs text-gray-600">📡</span>}
              {fuente === "orquestador" && <span className="text-xs text-gray-600">🧠</span>}
            </div>
          );
        })}
      </div>

      {Object.keys(nivelLocal).length === 0 && Object.keys(nivelOrq).length === 0 && (
        <p className="text-xs text-gray-600 mt-2 text-center">
          Conectando con el Agente de Gases…
        </p>
      )}
    </div>
  );
}
