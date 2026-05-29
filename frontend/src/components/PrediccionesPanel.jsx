/**
 * PrediccionesPanel.jsx — Predicciones LSTM automáticas del Agente de Gases.
 *
 * Cada 30 s toma la última lectura del historial del Agente de Gases y
 * llama a /analizar para obtener las predicciones de los próximos 90 min.
 * Si no hay suficiente historial (< 24 lecturas) lo indica claramente.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";

const AGENTE_GAS = import.meta.env.VITE_AGENTE_GAS || "http://localhost:8001";
const ZONAS = ["Frente_A_Sogamoso", "Frente_B_Mongua", "Galeria_Central", "Bocamina"];
const GASES = ["CH4", "CO", "CO2", "O2", "H2S"];

// Umbrales mínimos para colorear celdas de predicción
const UMBRAL_ALERTA = {
  CH4: 0.5, CO: 25, CO2: 0.5, H2S: 1,
  O2_MIN: 19.5,   // O2 alerta si cae por debajo
};

function colorCelda(gas, valor) {
  if (valor == null) return "text-gray-500";
  if (gas === "O2") {
    if (valor < 17)   return "text-red-400 font-bold";
    if (valor < 19.5) return "text-yellow-400 font-bold";
    return "text-green-400";
  }
  const umbral = UMBRAL_ALERTA[gas];
  if (!umbral) return "text-gray-300";
  if (valor >= umbral * 3) return "text-red-400 font-bold";
  if (valor >= umbral * 1.5) return "text-orange-400 font-bold";
  if (valor >= umbral) return "text-yellow-400 font-semibold";
  return "text-green-400";
}

function fmt(gas, valor) {
  if (valor == null) return "–";
  return typeof valor === "number"
    ? valor.toFixed(gas === "CO" || gas === "H2S" ? 1 : 3)
    : String(valor);
}

// Mini barra horizontal proporcional al umbral
function MiniBarra({ gas, valor }) {
  const maxes = { CH4: 2, CO: 150, CO2: 2, O2: 25, H2S: 30 };
  const max = maxes[gas] || 100;
  const pct = Math.min(100, Math.max(0, (valor / max) * 100));
  const color = colorCelda(gas, valor).includes("red")
    ? "bg-red-500" : colorCelda(gas, valor).includes("orange")
    ? "bg-orange-400" : colorCelda(gas, valor).includes("yellow")
    ? "bg-yellow-400" : "bg-green-500";
  return (
    <div className="w-full bg-gray-700 rounded-full h-1 mt-0.5">
      <div className={`h-1 rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function PrediccionesPanel({ zona: zonaWS }) {
  const [zona,          setZona]          = useState(zonaWS || ZONAS[0]);
  const [predicciones,  setPredicciones]  = useState([]);  // array de 6 pasos
  const [estado,        setEstado]        = useState("idle"); // idle | cargando | ok | sin_historial | sin_modelo | error
  const [ultimaActualiz,setUltimaActualiz]= useState(null);
  const [lecturaBase,   setLecturaBase]   = useState(null);
  const [historialCount,setHistorialCount]= useState(0);
  const timerRef = useRef(null);

  // Si la zona cambia por WebSocket, sincronizar
  useEffect(() => {
    if (zonaWS && zonaWS !== zona) setZona(zonaWS);
  }, [zonaWS]);

  const cargarPredicciones = useCallback(async (z) => {
    setEstado("cargando");
    try {
      // 1. Obtener última lectura del historial
      const histResp = await fetch(`${AGENTE_GAS}/historial/${z}?n=1`);
      if (!histResp.ok) throw new Error(`HTTP ${histResp.status} en /historial`);
      const histData = await histResp.json();
      const lista = histData.lecturas || histData;

      if (!Array.isArray(lista) || lista.length === 0) {
        setEstado("sin_historial");
        setHistorialCount(0);
        return;
      }

      // 2. Obtener conteo real del historial para saber si LSTM puede predecir
      const histFullResp = await fetch(`${AGENTE_GAS}/historial/${z}?n=500`);
      if (histFullResp.ok) {
        const fullData = await histFullResp.json();
        const fullLista = fullData.lecturas || fullData;
        setHistorialCount(Array.isArray(fullLista) ? fullLista.length : 0);
        if (Array.isArray(fullLista) && fullLista.length < 24) {
          setEstado("sin_historial");
          setHistorialCount(fullLista.length);
          setLecturaBase(lista[lista.length - 1]);
          return;
        }
      }

      const ultima = lista[lista.length - 1];
      setLecturaBase(ultima);

      // 3. Llamar a /analizar con esa lectura
      const analResp = await fetch(`${AGENTE_GAS}/analizar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          zona:          z,
          CH4:           ultima.CH4  ?? 0,
          CO:            ultima.CO   ?? 0,
          CO2:           ultima.CO2  ?? 0,
          O2:            ultima.O2   ?? 20.8,
          H2S:           ultima.H2S  ?? 0,
          temperatura_C: ultima.temperatura_C ?? 22,
          humedad_pct:   ultima.humedad_pct   ?? 75,
        }),
      });
      if (!analResp.ok) throw new Error(`HTTP ${analResp.status} en /analizar`);
      const analData = await analResp.json();

      const preds = analData.predicciones || [];
      setPredicciones(preds);
      setUltimaActualiz(new Date().toLocaleTimeString("es-CO"));
      if (preds.length > 0) {
        setEstado("ok");
      } else {
        // Hay historial suficiente pero el modelo LSTM no está entrenado/cargado
        setEstado("sin_modelo");
      }
    } catch (e) {
      setEstado("error");
      console.error("PrediccionesPanel:", e.message);
    }
  }, []);

  // Arrancar y refrescar cada 30 s
  useEffect(() => {
    cargarPredicciones(zona);
    timerRef.current = setInterval(() => cargarPredicciones(zona), 30_000);
    return () => clearInterval(timerRef.current);
  }, [zona, cargarPredicciones]);

  // ── Construir filas de la tabla: columnas = pasos, filas = gases ─────────────
  const pasos = Array.from({ length: 6 }, (_, i) => {
    const minutos = (i + 1) * 15;
    const hora = new Date(Date.now() + minutos * 60_000)
      .toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
    const pred = predicciones[i];
    return { minutos, hora, pred };
  });

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="bg-gray-900 rounded-xl p-4 border border-gray-700">
      {/* Cabecera */}
      <div className="flex justify-between items-center mb-3 flex-wrap gap-2">
        <div>
          <h2 className="font-bold text-lg">📈 Predicciones LSTM</h2>
          <p className="text-xs text-gray-400">
            Próximos 90 min · 6 pasos × 15 min
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Selector de zona */}
          <select
            value={zona}
            onChange={(e) => setZona(e.target.value)}
            className="bg-gray-800 border border-gray-600 rounded-lg px-2 py-1 text-xs text-white
                       focus:outline-none focus:border-blue-500"
          >
            {ZONAS.map((z) => (
              <option key={z} value={z}>{z.replace(/_/g, " ")}</option>
            ))}
          </select>
          {/* Botón refrescar */}
          <button
            onClick={() => cargarPredicciones(zona)}
            disabled={estado === "cargando"}
            className="text-xs bg-gray-800 hover:bg-gray-700 border border-gray-600
                       px-2 py-1 rounded-lg disabled:opacity-50"
          >
            {estado === "cargando" ? "⏳" : "🔄"}
          </button>
        </div>
      </div>

      {/* ── Estado: error ── */}
      {estado === "error" && (
        <div className="bg-red-950 border border-red-800 rounded-lg p-3 text-sm text-red-300">
          ⚠ No se pudo conectar al Agente de Gases (puerto 8001).
          <p className="text-xs mt-1 text-red-400">
            Verifica que el agente esté corriendo: <code>uvicorn backend.agentes.gases.app:app --port 8001</code>
          </p>
        </div>
      )}

      {/* ── Estado: modelo LSTM no entrenado ── */}
      {estado === "sin_modelo" && (
        <div className="space-y-3">
          {/* Aviso principal */}
          <div className="bg-blue-950 border border-blue-700 rounded-lg p-4">
            <p className="text-sm font-bold text-blue-300 mb-1">
              🤖 Modelos LSTM no entrenados aún
            </p>
            <p className="text-xs text-blue-200 leading-relaxed">
              Hay <strong>{historialCount} lecturas</strong> en el historial (suficiente para predecir),
              pero los archivos <code className="bg-blue-900 px-1 rounded">.keras</code> no se encontraron
              en <code className="bg-blue-900 px-1 rounded">modelos/gases/</code>.
            </p>
          </div>

          {/* Mientras tanto: mostrar tendencia con los datos reales */}
          {lecturaBase && (
            <div className="bg-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-400 font-semibold mb-2">
                📊 Última lectura disponible (base para tendencia):
              </p>
              <div className="grid grid-cols-5 gap-2">
                {[
                  { g: "CH4", label: "CH₄", unit: "%",   val: lecturaBase.CH4 },
                  { g: "CO",  label: "CO",  unit: "ppm", val: lecturaBase.CO  },
                  { g: "CO2", label: "CO₂", unit: "%",   val: lecturaBase.CO2 },
                  { g: "O2",  label: "O₂",  unit: "%",   val: lecturaBase.O2  },
                  { g: "H2S", label: "H₂S", unit: "ppm", val: lecturaBase.H2S },
                ].map(({ g, label, unit, val }) => (
                  <div key={g} className="text-center bg-gray-700 rounded p-2">
                    <p className="text-xs text-gray-400">{label}</p>
                    <p className={`text-sm font-bold ${colorCelda(g, val)}`}>
                      {val != null ? (val.toFixed(g === "CO" || g === "H2S" ? 1 : 3)) : "–"}
                    </p>
                    <p className="text-xs text-gray-500">{unit}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Instrucciones para entrenar */}
          <div className="bg-gray-800 rounded-lg p-3 text-xs text-gray-400">
            <p className="font-semibold text-gray-300 mb-1">
              ¿Por qué no aparecen predicciones?
            </p>
            <p className="mb-1">
              Los modelos están en{" "}
              <code className="bg-gray-700 px-1 rounded">modelos_reparados/gases/</code>{" "}
              pero TensorFlow puede no estar instalado o los modelos tienen un formato incompatible.
            </p>
            <p className="font-semibold text-gray-300 mt-2 mb-1">Diagnóstico rápido:</p>
            <p className="mb-1">
              Abre <code className="bg-gray-700 px-1 rounded">http://localhost:8001/predictor/status</code>{" "}
              en el navegador para ver el estado exacto del predictor.
            </p>
            <p className="font-semibold text-gray-300 mt-2 mb-1">Si TensorFlow no está instalado:</p>
            <p className="text-gray-500 ml-2">pip install tensorflow</p>
            <p className="font-semibold text-gray-300 mt-2 mb-1">Si los modelos son incompatibles:</p>
            <p className="text-gray-500 ml-2">
              Vuelve a ejecutar <code className="bg-gray-700 px-1 rounded">ENTRENAR_LSTM_GASES.ipynb</code> en Colab
              y descarga el ZIP a <code className="bg-gray-700 px-1 rounded">modelos_reparados/gases/</code>.
            </p>
          </div>
        </div>
      )}

      {/* ── Estado: sin historial suficiente ── */}
      {estado === "sin_historial" && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 text-center">
          <p className="text-4xl mb-2">📊</p>
          <p className="text-sm text-gray-300 font-medium">
            Historial insuficiente para predecir
          </p>
          <p className="text-xs text-gray-500 mt-1">
            El modelo LSTM necesita <strong className="text-gray-300">al menos 24 lecturas</strong> acumuladas.
          </p>
          {historialCount > 0 && (
            <div className="mt-3">
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all"
                  style={{ width: `${Math.min(100, (historialCount / 24) * 100)}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">
                {historialCount} / 24 lecturas ({Math.round((historialCount / 24) * 100)}%)
              </p>
            </div>
          )}
          <p className="text-xs text-blue-400 mt-2">
            Inicia la simulación para acumular historial (~6 min a 15 s/ciclo)
          </p>
          {lecturaBase && (
            <p className="text-xs text-gray-500 mt-1">
              Última lectura disponible: CH₄={lecturaBase.CH4?.toFixed(3)}% · CO={lecturaBase.CO?.toFixed(1)} ppm
            </p>
          )}
        </div>
      )}

      {/* ── Estado: cargando primera vez ── */}
      {estado === "cargando" && predicciones.length === 0 && (
        <div className="text-center py-6">
          <div className="animate-spin text-2xl mb-2">⏳</div>
          <p className="text-gray-400 text-sm">Consultando predicciones…</p>
        </div>
      )}

      {/* ── Estado: predicciones disponibles ── */}
      {estado === "ok" && predicciones.length > 0 && (
        <>
          {/* Tabla de predicciones */}
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left text-gray-400 pb-2 pr-3 font-medium">Gas</th>
                  {pasos.map(({ minutos, hora }) => (
                    <th key={minutos} className="text-center text-gray-400 pb-2 px-1 font-medium whitespace-nowrap">
                      +{minutos}'<br />
                      <span className="text-gray-600 font-normal">{hora}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {GASES.map((gas) => (
                  <tr key={gas} className="border-b border-gray-800">
                    <td className="py-2 pr-3 text-gray-300 font-medium whitespace-nowrap">
                      {gas === "CH4" ? "CH₄ (%)" :
                       gas === "CO"  ? "CO (ppm)" :
                       gas === "CO2" ? "CO₂ (%)" :
                       gas === "O2"  ? "O₂ (%)" :
                                       "H₂S (ppm)"}
                    </td>
                    {pasos.map(({ minutos, pred }) => {
                      const val = pred?.gases_predichos?.[gas] ?? null;
                      return (
                        <td key={minutos} className="py-2 px-1 text-center">
                          <span className={colorCelda(gas, val)}>
                            {fmt(gas, val)}
                          </span>
                          {val != null && <MiniBarra gas={gas} valor={val} />}
                        </td>
                      );
                    })}
                  </tr>
                ))}
                {/* Fila de nivel predicho */}
                <tr>
                  <td className="pt-2 pr-3 text-gray-400 font-medium text-xs">Nivel</td>
                  {pasos.map(({ minutos, pred }) => {
                    const nv = pred?.nivel_predicho || "–";
                    const cls =
                      nv.includes("EVACUACIÓN") ? "bg-purple-800 text-purple-100" :
                      nv.includes("EMERGENCIA") ? "bg-red-800 text-red-100"       :
                      nv.includes("ALTO")       ? "bg-orange-700 text-orange-100" :
                      nv.includes("PRECAUCIÓN") ? "bg-yellow-700 text-yellow-100" :
                      nv !== "–"                ? "bg-green-800 text-green-100"   :
                                                  "text-gray-600";
                    return (
                      <td key={minutos} className="pt-2 px-1 text-center">
                        {nv !== "–" ? (
                          <span className={`inline-block px-1 py-0.5 rounded text-xs font-bold ${cls}`}>
                            {nv.replace("EVACUACIÓN INMEDIATA", "EVAC.").replace("RIESGO ALTO", "ALTO")}
                          </span>
                        ) : (
                          <span className="text-gray-600">–</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              </tbody>
            </table>
          </div>

          {/* Alertas predictivas destacadas */}
          {predicciones.some((p) => p.alertas && p.alertas.length > 0) && (
            <div className="mt-3 bg-orange-950 border border-orange-700 rounded-lg p-3">
              <p className="text-xs font-bold text-orange-300 mb-1">
                ⚠ Alertas predictivas detectadas:
              </p>
              {predicciones.map((p, i) =>
                p.alertas && p.alertas.length > 0 ? (
                  <p key={i} className="text-xs text-orange-200">
                    • +{(i + 1) * 15} min: {p.alertas.join(", ")} supera umbral
                  </p>
                ) : null
              )}
            </div>
          )}

          {/* Pie con lectura base y timestamp */}
          <div className="mt-3 flex justify-between text-xs text-gray-600">
            <span>
              Base:{" "}
              {lecturaBase
                ? `CH₄=${lecturaBase.CH4?.toFixed(3)}% · CO=${lecturaBase.CO?.toFixed(1)} ppm`
                : "–"}
            </span>
            <span>Actualizado: {ultimaActualiz}</span>
          </div>
        </>
      )}
    </div>
  );
}
