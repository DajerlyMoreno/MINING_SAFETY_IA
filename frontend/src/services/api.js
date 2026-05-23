/**
 * api.js — Cliente HTTP centralizado para comunicarse con el Orquestador.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const WS_URL   = import.meta.env.VITE_WS_URL  || "ws://localhost:8000/ws/eventos";

export const api = {
  // ── Orquestador ────────────────────────────────────────────────────────────
  orquestar: (payload) =>
    fetch(`${BASE_URL}/orquestar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then((r) => r.json()),

  obtenerEstado: () => fetch(`${BASE_URL}/estado`).then((r) => r.json()),

  obtenerHistorial: (n = 20, zona = null) => {
    const params = new URLSearchParams({ n });
    if (zona) params.append("zona", zona);
    return fetch(`${BASE_URL}/historial?${params}`).then((r) => r.json());
  },

  consultarRAG: (query, k = 3, categoria = null) =>
    fetch(`${BASE_URL}/rag/consultar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, k, categoria }),
    }).then((r) => r.json()),

  // ── Simulador ─────────────────────────────────────────────────────────────
  simularCiclo: (zona, evento = false) =>
    fetch(`http://localhost:8005/simular?zona=${zona}&evento=${evento}`, {
      method: "POST",
    }).then((r) => r.json()),

  iniciarSimulacion: () =>
    fetch("http://localhost:8005/iniciar", { method: "POST" }).then((r) => r.json()),
};

export { WS_URL };