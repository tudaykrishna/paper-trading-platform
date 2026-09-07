import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../store/auth";
import { useQuoteStore } from "../store/quotes";

const wsBase =
  (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/^http/, "ws");

/**
 * Single app WebSocket. Streams live ticks into the quote store and invalidates
 * order/position queries when the engine reports a fill.
 *
 * The connection always reads the CURRENT access token from the store (not a
 * closed-over copy), and on an auth-close (4401) it refreshes the token before
 * reconnecting — otherwise the live feed dies silently after the 30-min token
 * expiry.
 */
export function useMarketSocket(subscribeKeys: string[]) {
  const loggedIn = useAuthStore((s) => !!s.accessToken);
  const upsert = useQuoteStore((s) => s.upsert);
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const keysRef = useRef<string[]>(subscribeKeys);

  useEffect(() => {
    if (!loggedIn) return;
    let stopped = false;
    let retry: ReturnType<typeof setTimeout>;

    const connect = async () => {
      if (stopped) return;
      let token = useAuthStore.getState().accessToken;
      if (!token) token = await useAuthStore.getState().refresh();
      if (!token || stopped) return;

      const ws = new WebSocket(`${wsBase}/ws?token=${token}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (keysRef.current.length)
          ws.send(JSON.stringify({ action: "set", keys: keysRef.current }));
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "tick") {
            const d = msg.data;
            upsert({
              instrument_key: d.instrument_key,
              ltp: Number(d.ltp),
              prev_close: d.prev_close != null ? Number(d.prev_close) : null,
              open: d.open != null ? Number(d.open) : null,
              ts: d.ts,
            });
          } else if (msg.type === "order") {
            qc.invalidateQueries({ queryKey: ["orders"] });
            qc.invalidateQueries({ queryKey: ["trades"] });
          } else if (msg.type === "position") {
            ["positions", "holdings", "funds", "summary"].forEach((k) =>
              qc.invalidateQueries({ queryKey: [k] }),
            );
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = async (ev) => {
        if (stopped) return;
        if (ev.code === 4401) {
          // token rejected — mint a fresh one before retrying
          await useAuthStore.getState().refresh();
        }
        retry = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, [loggedIn, upsert, qc]);

  useEffect(() => {
    keysRef.current = subscribeKeys;
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ action: "set", keys: subscribeKeys }));
    }
  }, [subscribeKeys.join(",")]);
}
