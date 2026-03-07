"use client";

import { useEffect, useRef, useCallback } from "react";
import { WsEvent } from "@/types/invoice";

const WS_URL =
  (process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000") + "/ws/processing";

type WsHandler = (event: WsEvent) => void;

export function useWebSocket(onEvent: WsHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const handlerRef = useRef(onEvent);
  handlerRef.current = onEvent;

  const connect = useCallback(() => {
    if (typeof window === "undefined") return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as WsEvent;
        handlerRef.current(data);
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      // Reconnect after 2s on disconnect
      setTimeout(() => {
        if (wsRef.current === ws) connect();
      }, 2000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => {
      const ws = wsRef.current;
      if (ws) {
        wsRef.current = null;
        ws.close();
      }
    };
  }, [connect]);
}
