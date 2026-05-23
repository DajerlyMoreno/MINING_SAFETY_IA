/**
 * App.jsx — Componente raíz del Dashboard de Monitoreo Minero.
 */

import React, { useState, useEffect } from "react";
import { RiskMap }      from "./components/RiskMap";
import { AlertPanel }   from "./components/AlertPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import { api }          from "./services/api";

const NIVEL_COLORES_BG = {
  SEGURO: "bg-green-900", INFORMATIVO: "bg-blue-900",
  "PRECAUCIÓN": "bg-yellow-900", "RIESGO ALTO": "bg-red-900",
  EMERGENCIA: "bg-red-950", "EVACUACIÓN INMEDIATA": "bg-purple-950",
};

export default function App() {
  const { eventos, ultimoEvento, conectado, nivelActual } = useWebSocket();
  const [estado, setEstado] = useState(null);
  const [simulando, setSimulando] = useState(false);

  // Polling del estado del sistema cada 10s
  useEffect(() => {
    const cargarEstado = async () => {
      try { setEstado(await api.obtenerEstado()); } catch { /* offline */ }
    };
    cargarEstado();
    const id = setInterval(cargarEstado, 10_000);
    return () => clearInterval(id);
  }, []);

  const iniciarSim = async () => {
    await api.iniciarSimulacion();
    setSimulando(true);
  };

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4">
      {/* Header */}
      <div className={`rounded-xl p-4 mb-4 ${NIVEL_COLORES_BG[nivelActual] || "bg-gray-900"}`}>
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold">
              🏭 Sistema Multiagente — Minería Subterránea UPTC 2026
            </h1>
            <p className="text-sm opacity-80">
              Estado: <strong>{nivelActual}</strong> |
              WS: {conectado ? "🟢 Conectado" : "🔴 Desconectado"} |
              Eventos: {eventos.length}
            </p>
          </div>
          <button
            onClick={iniciarSim}
            disabled={simulando}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                       px-4 py-2 rounded-lg font-bold text-sm"
          >
            {simulando ? "⏳ Simulando..." : "▶ Iniciar Simulación"}
          </button>
        </div>
      </div>

      {/* Grid principal */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Mapa de riesgo */}
        <div className="lg:col-span-2">
          <RiskMap eventos={eventos} />
        </div>

        {/* Estado de agentes */}
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
          <h2 className="font-bold text-lg mb-3">📡 Estado Agentes</h2>
          {estado?.agentes && Object.entries(estado.agentes).map(([nombre, est]) => (
            <div key={nombre}
              className="flex justify-between py-1 border-b border-gray-800 text-sm">
              <span className="text-gray-300">{nombre.replace("AGENTE_","")}</span>
              <span className={est === "ACTIVO" ? "text-green-400" : "text-red-400"}>
                {est === "ACTIVO" ? "🟢" : "🔴"} {est}
              </span>
            </div>
          ))}
          {estado && (
            <div className="mt-3 text-xs text-gray-500 space-y-1">
              <p>Ciclos: {estado.estadisticas?.ciclos || 0}</p>
              <p>Evacuaciones: {estado.estadisticas?.evacuaciones || 0}</p>
              <p>Correlaciones: {estado.estadisticas?.correlaciones || 0}</p>
            </div>
          )}
        </div>

        {/* Panel de alertas */}
        <div className="lg:col-span-2">
          <AlertPanel eventos={eventos} />
        </div>

        {/* Último evento */}
        {ultimoEvento && (
          <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
            <h2 className="font-bold text-lg mb-2">📋 Último Evento</h2>
            <p className="text-xs text-gray-400 mb-2">[{ultimoEvento.id_evento}]</p>
            <p className="text-sm font-medium">{ultimoEvento.prediccion}</p>
            <div className="mt-2 max-h-32 overflow-y-auto">
              {ultimoEvento.acciones_globales?.slice(0,4).map((a, i) => (
                <p key={i} className="text-xs text-gray-300 mt-1">• {a}</p>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}