import { useEffect, useRef, useState, useCallback } from "react";

export interface HealthCheckMessage {
  type: "health_check";
  service_id: string;
  status: "healthy" | "degraded" | "down";
  response_time_ms: number | null;
  checked_at: string;
}

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const WS_URL = BASE_URL.replace(/^http/, "ws") + "/ws/status";

const INITIAL_DELAY = 1000;
const MAX_DELAY = 30000;

export function useWebSocket(onMessage: (msg: HealthCheckMessage) => void) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const delayRef = useRef(INITIAL_DELAY);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      delayRef.current = INITIAL_DELAY;
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as HealthCheckMessage;
        onMessageRef.current(data);
      } catch {
        // ignore non-JSON messages
      }
    };

    ws.onclose = () => {
      setConnected(false);
      wsRef.current = null;
      // Schedule reconnection with exponential backoff
      const delay = delayRef.current;
      delayRef.current = Math.min(delay * 2, MAX_DELAY);
      timerRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnection
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { connected };
}
