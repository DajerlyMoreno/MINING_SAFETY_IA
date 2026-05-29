/**
 * api.js — Cliente HTTP centralizado para comunicarse con el Orquestador.
 */

const BASE_URL     = import.meta.env.VITE_API_URL     || "http://localhost:8000";
const SIM_URL      = import.meta.env.VITE_SIM_URL     || "http://localhost:8005";
const AGENTE_GAS   = import.meta.env.VITE_AGENTE_GAS  || "http://localhost:8001";
export const WS_URL = import.meta.env.VITE_WS_URL     || "ws://localhost:8000/ws/eventos";

const json = (r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); };

export const api = {
  // ── Orquestador ────────────────────────────────────────────────────────────
  orquestar: (payload) =>
    fetch(`${BASE_URL}/orquestar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(json),

  obtenerEstado: () => fetch(`${BASE_URL}/estado`).then(json),

  obtenerHistorial: (n = 20, zona = null) => {
    const p = new URLSearchParams({ n });
    if (zona) p.append("zona", zona);
    return fetch(`${BASE_URL}/historial?${p}`).then(json);
  },

  consultarRAG: (query, k = 3, categoria = null) =>
    fetch(`${BASE_URL}/rag/consultar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k, categoria }),
    }).then(json),

  // ── Simulador ─────────────────────────────────────────────────────────────
  iniciarSimulacion: () =>
    fetch(`${SIM_URL}/iniciar`, { method: "POST" }).then(json),

  detenerSimulacion: () =>
    fetch(`${SIM_URL}/detener`, { method: "POST" }).then(json),

  // ── Agente de Gases ───────────────────────────────────────────────────────
  /** Envía una lectura manual y obtiene el análisis completo */
  analizarLectura: (zona, CH4, CO, CO2, O2, H2S, temperatura_C = 22, humedad_pct = 75) =>
    fetch(`${AGENTE_GAS}/analizar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ zona, CH4, CO, CO2, O2, H2S, temperatura_C, humedad_pct }),
    }).then(json),

  historialGas: (zona, n = 50) =>
    fetch(`${AGENTE_GAS}/historial/${zona}?n=${n}`).then(json),
};
