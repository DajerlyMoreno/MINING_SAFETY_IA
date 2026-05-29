/**
 * GasPanel.jsx — Lecturas actuales de gases con referencia al Decreto 1886/2015.
 *
 * Estrategia de datos (doble fuente, sin dependencia exclusiva del WebSocket):
 *   1. Polling directo al Agente de Gases (:8001/historial/{zona}) cada 4 s.
 *   2. Si llega un evento por WebSocket (prop ultimoEvento), se prioriza porque
 *      es más reciente y ya viene procesado por el orquestador.
 */

import React, { useState, useEffect, useRef } from "react";

const AGENTE_GAS = import.meta.env.VITE_AGENTE_GAS || "http://localhost:8001";
const ZONAS = ["Frente_A_Sogamoso", "Frente_B_Mongua", "Galeria_Central", "Bocamina"];
const GASES = ["CH4", "CO", "CO2", "O2", "H2S"];

// ─── Umbrales y artículos del Decreto 1886/2015 ───────────────────────────────
const DECRETO = {
  CH4: {
    nombre: "Metano (CH₄)", unidad: "%",
    niveles: [
      { umbral: 1.5, nivel: "EVACUACIÓN INMEDIATA", articulo: "Art. 65",
        descripcion: "CH₄ ≥ 1.5 %: riesgo de explosión inminente. Evacuación total obligatoria." },
      { umbral: 1.0, nivel: "EMERGENCIA", articulo: "Art. 65",
        descripcion: "CH₄ ≥ 1.0 %: suspender actividades y activar ventilación de emergencia." },
      { umbral: 0.5, nivel: "PRECAUCIÓN", articulo: "Art. 64",
        descripcion: "CH₄ ≥ 0.5 %: notificar jefe de turno y aumentar caudal de ventilación." },
    ],
    normal: "< 0.5 %  (Art. 64)",
    maxBarra: 2.0,
  },
  CO: {
    nombre: "Monóxido de Carbono (CO)", unidad: "ppm",
    niveles: [
      { umbral: 100, nivel: "EMERGENCIA", articulo: "Art. 66",
        descripcion: "CO ≥ 100 ppm: riesgo de intoxicación grave. Evacuar el frente." },
      { umbral: 50, nivel: "RIESGO ALTO", articulo: "Art. 66",
        descripcion: "CO ≥ 50 ppm: TLV-TWA superado. Preparar auto-rescatadores." },
      { umbral: 25, nivel: "PRECAUCIÓN", articulo: "Art. 66",
        descripcion: "CO ≥ 25 ppm: advertencia temprana. Verificar fuentes de combustión." },
    ],
    normal: "< 25 ppm  (Art. 66)",
    maxBarra: 150,
  },
  CO2: {
    nombre: "Dióxido de Carbono (CO₂)", unidad: "%",
    niveles: [
      { umbral: 1.5, nivel: "EMERGENCIA", articulo: "Art. 67",
        descripcion: "CO₂ ≥ 1.5 %: riesgo de asfixia. Evacuar inmediatamente." },
      { umbral: 1.0, nivel: "RIESGO ALTO", articulo: "Art. 67",
        descripcion: "CO₂ ≥ 1.0 %: ventilación insuficiente. Activar sistemas auxiliares." },
      { umbral: 0.5, nivel: "PRECAUCIÓN", articulo: "Art. 67",
        descripcion: "CO₂ ≥ 0.5 %: incremento anormal. Revisar ventilación principal." },
    ],
    normal: "< 0.5 %  (Art. 67)",
    maxBarra: 2.0,
  },
  O2: {
    nombre: "Oxígeno (O₂)", unidad: "%",
    niveles: [
      { umbral: 16.0, nivel: "EVACUACIÓN INMEDIATA", articulo: "Art. 68", comparador: "<",
        descripcion: "O₂ < 16.0 %: peligro inmediato de vida. Evacuar con equipo autónomo." },
      { umbral: 17.0, nivel: "EMERGENCIA", articulo: "Art. 68", comparador: "<",
        descripcion: "O₂ < 17.0 %: deficiencia severa. Activar brigada de rescate." },
      { umbral: 19.5, nivel: "PRECAUCIÓN", articulo: "Art. 68", comparador: "<",
        descripcion: "O₂ < 19.5 %: deficiencia de oxígeno. Aumentar ventilación." },
    ],
    normal: "19.5 – 23.0 %  (Art. 68)",
    maxBarra: 25,
  },
  H2S: {
    nombre: "Sulfuro de Hidrógeno (H₂S)", unidad: "ppm",
    niveles: [
      { umbral: 20, nivel: "EMERGENCIA", articulo: "Art. 69",
        descripcion: "H₂S ≥ 20 ppm: gas muy tóxico. Evacuación inmediata con equipo autónomo." },
      { umbral: 10, nivel: "RIESGO ALTO", articulo: "Art. 69",
        descripcion: "H₂S ≥ 10 ppm: TLV-TWA superado. Suspender actividades en el área." },
      { umbral: 1, nivel: "PRECAUCIÓN", articulo: "Art. 69",
        descripcion: "H₂S ≥ 1 ppm: olor detectado. Verificar origen e incrementar ventilación." },
    ],
    normal: "< 1 ppm  (Art. 69)",
    maxBarra: 30,
  },
};

function evaluarGas(gas, valor) {
  const def = DECRETO[gas];
  if (!def || valor == null) return null;
  for (const n of def.niveles) {
    const critico = n.comparador === "<" ? valor < n.umbral : valor >= n.umbral;
    if (critico) return { ...n, gas, nombre: def.nombre, unidad: def.unidad, valor };
  }
  return null;
}

const NIVEL_BG = {
  "EVACUACIÓN INMEDIATA": "bg-purple-950 border-purple-700",
  EMERGENCIA:             "bg-red-950   border-red-700",
  "RIESGO ALTO":          "bg-orange-950 border-orange-600",
  PRECAUCIÓN:             "bg-yellow-950 border-yellow-600",
};

// ─── Tarjeta individual ───────────────────────────────────────────────────────
function TarjetaGas({ gas, valor }) {
  const def   = DECRETO[gas];
  const alerta = evaluarGas(gas, valor);
  const bg    = alerta ? (NIVEL_BG[alerta.nivel] || "bg-gray-800 border-gray-700") : "bg-gray-800 border-gray-700";

  // Barra de nivel
  const pct = def
    ? Math.min(100, Math.max(0, (valor / def.maxBarra) * 100))
    : 0;
  const barColor = alerta
    ? alerta.nivel.includes("EVACUACIÓN") || alerta.nivel.includes("EMERGENCIA")
      ? "bg-red-500" : alerta.nivel.includes("ALTO") ? "bg-orange-500" : "bg-yellow-400"
    : "bg-green-500";

  return (
    <div className={`rounded-lg border p-3 transition-colors duration-500 ${bg}`}>
      {/* Cabecera */}
      <div className="flex justify-between items-start gap-2">
        <span className="text-xs text-gray-400 font-medium leading-tight">
          {def?.nombre || gas}
        </span>
        {alerta && (
          <span className="shrink-0 text-xs font-bold px-1.5 py-0.5 rounded bg-red-800 text-red-200">
            ⚠ {alerta.nivel}
          </span>
        )}
      </div>

      {/* Valor numérico */}
      <div className="mt-1 flex items-baseline gap-1">
        <span className="text-2xl font-bold tabular-nums">
          {typeof valor === "number"
            ? valor.toFixed(gas === "CO" || gas === "H2S" ? 1 : 3)
            : "–"}
        </span>
        <span className="text-sm text-gray-400">{def?.unidad}</span>
      </div>

      {/* Barra */}
      <div className="w-full bg-gray-700 rounded-full h-1.5 mt-1.5">
        <div
          className={`h-1.5 rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Explicación decreto o estado normal */}
      {alerta ? (
        <div className="mt-2 text-xs bg-black/30 rounded p-2 leading-relaxed text-gray-200">
          <span className="font-bold text-yellow-300">{alerta.articulo}: </span>
          {alerta.descripcion}
        </div>
      ) : (
        <p className="text-xs text-green-400 mt-1.5">✓ Normal — {def?.normal}</p>
      )}
    </div>
  );
}

// ─── Tabla de últimas lecturas ────────────────────────────────────────────────
const UMBRALES_COLOR = {
  CH4: (v) => v >= 1.5 ? "text-red-400" : v >= 0.5 ? "text-yellow-400" : "text-green-400",
  CO:  (v) => v >= 100  ? "text-red-400" : v >= 25  ? "text-yellow-400" : "text-green-400",
  CO2: (v) => v >= 1.5  ? "text-red-400" : v >= 0.5 ? "text-yellow-400" : "text-green-400",
  O2:  (v) => v < 17    ? "text-red-400" : v < 19.5 ? "text-yellow-400" : "text-green-400",
  H2S: (v) => v >= 20   ? "text-red-400" : v >= 1   ? "text-yellow-400" : "text-green-400",
};

function TablaHistorial({ zona }) {
  const [filas, setFilas] = useState([]);

  useEffect(() => {
    const cargar = async () => {
      try {
        const r = await fetch(`${AGENTE_GAS}/historial/${zona}?n=10`);
        if (!r.ok) return;
        const d = await r.json();
        const lista = d.lecturas || d;
        if (Array.isArray(lista)) setFilas([...lista].reverse());
      } catch { /* sin datos */ }
    };
    cargar();
    const id = setInterval(cargar, 5000);
    return () => clearInterval(id);
  }, [zona]);

  if (filas.length === 0)
    return <p className="text-xs text-gray-500 italic mt-2">Sin historial disponible todavía.</p>;

  return (
    <div className="overflow-x-auto mt-3">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400">
            <th className="text-left pb-1 pr-2 font-medium">#</th>
            <th className="text-right pb-1 px-2 font-medium">CH₄ %</th>
            <th className="text-right pb-1 px-2 font-medium">CO ppm</th>
            <th className="text-right pb-1 px-2 font-medium">CO₂ %</th>
            <th className="text-right pb-1 px-2 font-medium">O₂ %</th>
            <th className="text-right pb-1 pl-2 font-medium">H₂S ppm</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={i} className="border-b border-gray-800/60">
              <td className="py-1 pr-2 text-gray-500">{filas.length - i}</td>
              {["CH4","CO","CO2","O2","H2S"].map((g) => {
                const v = f[g] ?? null;
                const cls = v != null ? UMBRALES_COLOR[g](v) : "text-gray-500";
                return (
                  <td key={g} className={`py-1 px-2 text-right tabular-nums font-mono ${cls}`}>
                    {v != null ? v.toFixed(g === "CO" || g === "H2S" ? 1 : 3) : "–"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Panel principal ──────────────────────────────────────────────────────────
export function GasPanel({ ultimoEvento }) {
  const [zonaSeleccionada, setZonaSeleccionada] = useState(ZONAS[0]);
  const [lecturas,  setLecturas]  = useState(null);   // valores { CH4, CO, CO2, O2, H2S }
  const [zona,      setZona]      = useState("—");
  const [nivel,     setNivel]     = useState("—");
  const [timestamp, setTimestamp] = useState("—");
  const [fuente,    setFuente]    = useState("polling"); // "websocket" | "polling"
  const [error,     setError]     = useState(null);
  const intervalRef = useRef(null);

  // ── 1. Prioridad: datos del WebSocket ────────────────────────────────────────
  useEffect(() => {
    if (!ultimoEvento) return;

    // El evento llega como msg.datos desde el orquestador
    const gasData = ultimoEvento.datos_gases || null;
    if (gasData && typeof gasData === "object") {
      setLecturas(gasData);
      setZona(ultimoEvento.zona || "—");
      setNivel(ultimoEvento.nivel_global || ultimoEvento.nivel_riesgo || "—");
      setTimestamp(
        ultimoEvento.timestamp
          ? new Date(ultimoEvento.timestamp).toLocaleTimeString("es-CO")
          : new Date().toLocaleTimeString("es-CO")
      );
      setFuente("websocket");
      setError(null);
    }
  }, [ultimoEvento]);

  // ── 2. Fallback: polling directo al Agente de Gases ──────────────────────────
  const fetchHistorial = async (z) => {
    try {
      const resp = await fetch(`${AGENTE_GAS}/historial/${z}?n=1`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      const lecturasList = data.lecturas || data;
      if (Array.isArray(lecturasList) && lecturasList.length > 0) {
        const ultima = lecturasList[lecturasList.length - 1];
        setLecturas(ultima);
        setZona(z);
        setTimestamp(new Date().toLocaleTimeString("es-CO"));
        setFuente("polling");
        setError(null);
        // Estimar nivel desde los gases
        const alertas = GASES.map((g) => evaluarGas(g, ultima[g])).filter(Boolean);
        if (alertas.length === 0) setNivel("SEGURO");
        else {
          const peor = alertas.sort((a, b) => {
            const ord = { PRECAUCIÓN: 1, "RIESGO ALTO": 2, EMERGENCIA: 3, "EVACUACIÓN INMEDIATA": 4 };
            return (ord[b.nivel] || 0) - (ord[a.nivel] || 0);
          })[0];
          setNivel(peor.nivel);
        }
      }
    } catch (e) {
      setError(`Agente de Gases no disponible (${e.message})`);
    }
  };

  // Arrancar polling al montar y al cambiar zona
  useEffect(() => {
    fetchHistorial(zonaSeleccionada);
    intervalRef.current = setInterval(() => fetchHistorial(zonaSeleccionada), 4000);
    return () => clearInterval(intervalRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zonaSeleccionada]);

  // Si llegan datos por WebSocket de otra zona, no anular la zona seleccionada
  // pero sí mostrarlos si coincide
  const alertasActivas = lecturas
    ? GASES.map((g) => evaluarGas(g, lecturas[g])).filter(Boolean)
    : [];

  // ── Render: sin datos todavía ─────────────────────────────────────────────
  if (!lecturas) {
    return (
      <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
        <div className="flex justify-between items-center mb-3">
          <h2 className="font-bold text-lg">🧪 Lectura Actual de Gases</h2>
          <ZonaSelector value={zonaSeleccionada} onChange={setZonaSeleccionada} />
        </div>
        {error ? (
          <div className="bg-red-950 border border-red-800 rounded-lg p-3 text-sm text-red-300">
            ⚠ {error}
            <p className="text-xs mt-1 text-red-400">
              Asegúrate de que el Agente de Gases esté corriendo en el puerto 8001.
            </p>
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="animate-spin text-3xl mb-3">⏳</div>
            <p className="text-gray-400 text-sm">Cargando lecturas de {zonaSeleccionada.replace(/_/g, " ")}…</p>
            <p className="text-gray-600 text-xs mt-1">
              Conectando al Agente de Gases (puerto 8001)
            </p>
          </div>
        )}
      </div>
    );
  }

  // ── Render: con datos ─────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
      {/* Cabecera */}
      <div className="flex justify-between items-center mb-3 gap-2 flex-wrap">
        <h2 className="font-bold text-lg">🧪 Lectura Actual de Gases</h2>
        <div className="flex items-center gap-3">
          <ZonaSelector value={zonaSeleccionada} onChange={setZonaSeleccionada} />
          <div className="text-right text-xs text-gray-400">
            <p>📍 {zona}</p>
            <p>🕐 {timestamp}</p>
            <p className={fuente === "websocket" ? "text-green-400" : "text-blue-400"}>
              {fuente === "websocket" ? "🔴 En vivo (WS)" : "🔄 Polling"}
            </p>
          </div>
        </div>
      </div>

      {/* Badge nivel global */}
      <div className={`rounded-lg px-3 py-1.5 text-center text-sm font-bold mb-3 ${
        nivel.includes("EVACUACIÓN") ? "bg-purple-800 text-purple-100" :
        nivel.includes("EMERGENCIA") ? "bg-red-800 text-red-100"       :
        nivel.includes("ALTO")       ? "bg-orange-700 text-orange-100" :
        nivel.includes("PRECAUCIÓN") ? "bg-yellow-700 text-yellow-100" :
                                       "bg-green-800 text-green-100"
      }`}>
        Nivel de riesgo: <strong>{nivel}</strong>
      </div>

      {/* Tarjetas de gases */}
      <div className="grid grid-cols-1 gap-2">
        {GASES.map((g) => (
          <TarjetaGas key={g} gas={g} valor={lecturas[g] ?? 0} />
        ))}
      </div>

      {/* Últimas 10 lecturas */}
      <div className="mt-3 border-t border-gray-700 pt-3">
        <p className="text-xs text-gray-400 font-semibold mb-1">
          📋 Últimas 10 lecturas — {zonaSeleccionada.replace(/_/g, " ")}
        </p>
        <TablaHistorial zona={zonaSeleccionada} />
      </div>
    </div>
  );
}

// ─── Selector de zona ─────────────────────────────────────────────────────────
function ZonaSelector({ value, onChange }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-xs text-white
                 focus:outline-none focus:border-blue-500"
    >
      {ZONAS.map((z) => (
        <option key={z} value={z}>{z.replace(/_/g, " ")}</option>
      ))}
    </select>
  );
}
