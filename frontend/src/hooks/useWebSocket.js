/**
 * useWebSocket.js — Hook React para recibir eventos del Orquestador en tiempo real.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { WS_URL } from "../services/api";

const NIVEL_ORDEN = {
  SEGURO: 0, INFORMATIVO: 1, "PRECAUCIÓN": 2,
  "RIESGO ALTO": 3, EMERGENCIA: 4, "EVACUACIÓN INMEDIATA": 5,
};

export function useWebSocket() {
  const [eventos,      setEventos]      = useState([]);
  const [ultimoEvento, setUltimoEvento] = useState(null);
  const [conectado,    setConectado]    = useState(false);
  const [nivelActual,  setNivelActual]  = useState("SEGURO");
  const wsRef = useRef(null);

  const conectar = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen  = () => { setConectado(true);  console.log("WS conectado"); };
    ws.onclose = () => { setConectado(false); console.log("WS desconectado");
                         setTimeout(conectar, 3000); };   // reconexión automática

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.tipo === "EVENTO_GLOBAL") {
        const evento = msg.datos;
        setUltimoEvento(evento);
        setNivelActual(evento.nivel_global);
        setEventos((prev) => [evento, ...prev].slice(0, 200));
      }
    };
  }, []);

  useEffect(() => {
    conectar();
    return () => wsRef.current?.close();
  }, [conectar]);

  return { eventos, ultimoEvento, conectado, nivelActual };
}