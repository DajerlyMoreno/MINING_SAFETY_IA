/**
 * App.jsx — Dashboard principal del Sistema Multiagente Minero.
 */

import React, { useState, useEffect } from "react";
import { RiskMap }           from "./components/RiskMap";
import { AlertPanel }        from "./components/AlertPanel";
import { GasPanel }          from "./components/GasPanel";
import { PrediccionesPanel } from "./components/PrediccionesPanel";
import { useWebSocket }      from "./hooks/useWebSocket";
import { api }               from "./services/api";

const NIVEL_COLORES_BG = {
  SEGURO:                 "bg-green-900",
  INFORMATIVO:            "bg-blue-900",
  "PRECAUCIÓN":           "bg-yellow-900",
  "RIESGO ALTO":          "bg-red-900",
  EMERGENCIA:             "bg-red-950",
  "EVACUACIÓN INMEDIATA": "bg-purple-950",
};

export default function App() {
  const { eventos, ultimoEvento, conectado, nivelActual } = useWebSocket();
  const [estado,    setEstado]    = useState(null);
  const [simulando, setSimulando] = useState(false);
  const [msgSim,    setMsgSim]    = useState("");
  const [tabActivo, setTabActivo] = useState("gases");

  useEffect(() => {
    const cargar = async () => {
      try { setEstado(await api.obtenerEstado()); } catch { /* offline */ }
    };
    cargar();
    const id = setInterval(cargar, 10_000);
    return () => clearInterval(id);
  }, []);

  const iniciarSim = async () => {
    try {
      await api.iniciarSimulacion();
      setSimulando(true);
      setMsgSim("Simulación iniciada");
      setTimeout(() => setMsgSim(""), 3000);
    } catch {
      setMsgSim("Error al iniciar simulación");
    }
  };

  const detenerSim = async () => {
    try {
      await api.detenerSimulacion();
      setSimulando(false);
      setMsgSim("Simulación detenida");
      setTimeout(() => setMsgSim(""), 3000);
    } catch {
      setSimulando(false);
      setMsgSim("Simulación marcada como detenida");
      setTimeout(() => setMsgSim(""), 3000);
    }
  };

  const bgHeader = NIVEL_COLORES_BG[nivelActual] || "bg-gray-900";

  return (
    <div className="min-h-screen bg-gray-950 text-white p-3">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className={`rounded-xl p-4 mb-4 ${bgHeader} transition-colors duration-700`}>
        <div className="flex flex-wrap justify-between items-center gap-2">
          <div>
            <h1 className="text-xl font-bold">
              ⛏ Sistema Multiagente — Minería Subterránea UPTC 2026
            </h1>
            <p className="text-xs opacity-80 mt-0.5">
              Nivel global: <strong>{nivelActual}</strong> &nbsp;|&nbsp;
              WS: {conectado ? "🟢 Conectado" : "🔴 Desconectado"} &nbsp;|&nbsp;
              Eventos recibidos: {eventos.length}
            </p>
          </div>

          <div className="flex items-center gap-2">
            {msgSim && (
              <span className="text-xs text-yellow-300 animate-pulse">{msgSim}</span>
            )}
            <button
              onClick={iniciarSim}
              disabled={simulando}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed
                         px-4 py-2 rounded-lg font-bold text-sm transition-colors"
            >
              ▶ Iniciar Simulación
            </button>
            <button
              onClick={detenerSim}
              disabled={!simulando}
              className="bg-red-700 hover:bg-red-800 disabled:opacity-40 disabled:cursor-not-allowed
                         px-4 py-2 rounded-lg font-bold text-sm transition-colors"
            >
              ⏹ Detener
            </button>
          </div>
        </div>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────────── */}
      <div className="flex gap-1 mb-4 bg-gray-900 rounded-xl p-1 border border-gray-800">
        {[
          { id: "gases",        label: "🧪 Gases en Tiempo Real" },
          { id: "predicciones", label: "📈 Predicciones LSTM" },
          { id: "mapa",         label: "🗺 Mapa de Riesgo" },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setTabActivo(tab.id)}
            className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
              tabActivo === tab.id
                ? "bg-blue-700 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Contenido ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* TAB: Gases en tiempo real */}
        {tabActivo === "gases" && (
          <>
            <div className="lg:col-span-2">
              <GasPanel ultimoEvento={ultimoEvento} />
            </div>
            <div className="flex flex-col gap-4">
              <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
                <h2 className="font-bold mb-3">📡 Estado Agentes</h2>
                {estado?.agentes
                  ? Object.entries(estado.agentes).map(([nombre, est]) => (
                    <div key={nombre}
                      className="flex justify-between py-1.5 border-b border-gray-800 text-sm">
                      <span className="text-gray-300">{nombre.replace("AGENTE_", "")}</span>
                      <span className={est === "ACTIVO" ? "text-green-400" : "text-red-400"}>
                        {est === "ACTIVO" ? "🟢" : "🔴"} {est}
                      </span>
                    </div>
                  ))
                  : <p className="text-gray-500 text-sm">Sin datos (orquestador offline)</p>
                }
                {estado && (
                  <div className="mt-3 text-xs text-gray-500 space-y-0.5">
                    <p>Ciclos: {estado.estadisticas?.ciclos || 0}</p>
                    <p>Evacuaciones: {estado.estadisticas?.evacuaciones || 0}</p>
                  </div>
                )}
              </div>

              {ultimoEvento && (
                <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
                  <h2 className="font-bold mb-2">📋 Último Evento</h2>
                  <p className="text-xs text-gray-400 mb-1">[{ultimoEvento.id_evento}]</p>
                  <p className="text-sm font-medium">{ultimoEvento.prediccion}</p>
                  <div className="mt-2 max-h-28 overflow-y-auto space-y-0.5">
                    {ultimoEvento.acciones_globales?.slice(0, 4).map((a, i) => (
                      <p key={i} className="text-xs text-gray-300">• {a}</p>
                    ))}
                  </div>
                </div>
              )}
            </div>

          </>
        )}

        {/* TAB: Predicciones LSTM */}
        {tabActivo === "predicciones" && (
          <div className="lg:col-span-3">
            <PrediccionesPanel zona={ultimoEvento?.zona} />
          </div>
        )}

        {/* TAB: Mapa de riesgo */}
        {tabActivo === "mapa" && (
          <>
            <div className="lg:col-span-2">
              <RiskMap eventos={eventos} />
            </div>
            <div className="lg:col-span-1">
              <AlertPanel eventos={eventos} />
            </div>
          </>
        )}

      </div>
    </div>
  );
}
