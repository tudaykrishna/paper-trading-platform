import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import { useAuthStore } from "../store/auth";
import { useQuoteStore } from "../store/quotes";

/* ---------- types ---------- */

export interface Me {
  id: number;
  email: string;
  name: string;
  is_active: boolean;
}
export interface Funds {
  cash_balance: string;
  blocked_margin: string;
  available_cash: string;
  opening_balance: string;
}
export interface LedgerEntry {
  id: number;
  ts: string;
  type: string;
  amount: string;
  balance_after: string;
  ref_order_id: number | null;
  note: string | null;
}
export interface Instrument {
  instrument_key: string;
  exchange: string;
  segment: string;
  instrument_type: string;
  category: string;
  tradingsymbol: string;
  name: string;
  lot_size: number;
  tick_size: string;
  expiry?: string | null;
  strike?: string | null;
  underlying_key?: string | null;
}
export interface Quote {
  instrument_key: string;
  ltp: string;
  prev_close?: string | null;
  change?: string | null;
  change_pct?: string | null;
  volume?: number | null;
  oi?: number | null;
}
export interface WatchlistItem {
  id: number;
  instrument_key: string;
  position: number;
  instrument: Instrument | null;
  quote: Quote | null;
}
export interface Watchlist {
  id: number;
  name: string;
  items: WatchlistItem[];
}
export interface Order {
  id: number;
  instrument_key: string;
  side: "BUY" | "SELL";
  qty: number;
  product: "CNC" | "MIS" | "NRML";
  order_type: "MARKET" | "LIMIT" | "SL" | "SL-M";
  validity: string;
  price: string | null;
  trigger_price: string | null;
  status: "PENDING" | "OPEN" | "COMPLETE" | "REJECTED" | "CANCELLED";
  filled_qty: number;
  avg_fill_price: string | null;
  blocked_margin: string;
  reject_reason: string | null;
  placed_at: string;
}
export interface Trade {
  id: number;
  order_id: number;
  instrument_key: string;
  side: string;
  qty: number;
  price: string;
  charges: string;
  charges_breakdown: Record<string, string>;
  net_amount: string;
  ts: string;
  trade_date: string;
}
export interface Position {
  instrument_key: string;
  product: string;
  trade_date: string;
  net_qty: number;
  avg_price: string;
  realized_pnl: string;
  blocked_margin: string;
  ltp: string | null;
  unrealized_pnl: string | null;
}
export interface Holding {
  instrument_key: string;
  qty: number;
  settled_qty: number;
  avg_price: string;
  realized_pnl: string;
  ltp: string | null;
  current_value: string | null;
  unrealized_pnl: string | null;
}
export interface OptionRow {
  strike: string;
  expiry: string;
  call_key: string | null;
  put_key: string | null;
  call_ltp: string | null;
  put_ltp: string | null;
  call_oi: number;
  put_oi: number;
}
export interface PlaceOrderBody {
  instrument_key: string;
  side: "BUY" | "SELL";
  qty: number;
  product: string;
  order_type: string;
  price?: string;
  trigger_price?: string;
  validity?: string;
}

/* ---------- queries ---------- */

export function useMe() {
  const token = useAuthStore((s) => s.accessToken);
  return useQuery({
    queryKey: ["me"],
    enabled: !!token,
    queryFn: async () => (await api.get<Me>("/api/auth/me")).data,
  });
}

export const useFunds = () =>
  useQuery({ queryKey: ["funds"], queryFn: async () => (await api.get<Funds>("/api/portfolio/funds")).data });

export const useLedger = () =>
  useQuery({
    queryKey: ["ledger"],
    queryFn: async () => (await api.get<LedgerEntry[]>("/api/portfolio/ledger")).data,
  });

export const useSummary = () =>
  useQuery({
    queryKey: ["summary"],
    refetchInterval: 5000,
    queryFn: async () => (await api.get<Record<string, string>>("/api/portfolio/summary")).data,
  });

export const useWatchlists = () =>
  useQuery({
    queryKey: ["watchlists"],
    // fallback refresh so prices stay current even if the WebSocket drops
    refetchInterval: 15_000,
    queryFn: async () => (await api.get<Watchlist[]>("/api/watchlists")).data,
  });

/**
 * Poll live quotes for a set of instruments and push them into the quote store.
 * A guaranteed fallback: the WebSocket streams tick-by-tick when it's up, this
 * keeps prices moving (every 4s) when it isn't.
 */
export function useQuotes(keys: string[]) {
  const seed = useQuoteStore((s) => s.seed);
  const csv = keys.join(",");
  return useQuery({
    queryKey: ["quotes", csv],
    enabled: keys.length > 0,
    refetchInterval: 4000,
    queryFn: async () => {
      const { data } = await api.get<Record<string, Quote>>("/api/instruments/quote", {
        params: { keys: csv },
      });
      seed(data as Record<string, { ltp: string; prev_close?: string | null; change?: string | null; change_pct?: string | null }>);
      return data;
    },
  });
}

export function useInstrumentSearch(q: string, opts?: { segment?: string; category?: string }) {
  return useQuery({
    queryKey: ["search", q, opts?.segment, opts?.category],
    enabled: q.length >= 1,
    queryFn: async () =>
      (
        await api.get<Instrument[]>("/api/instruments/search", {
          params: { q, segment: opts?.segment, category: opts?.category, limit: 25 },
        })
      ).data,
  });
}

export const useOrders = (openOnly = false) =>
  useQuery({
    queryKey: ["orders", openOnly],
    refetchInterval: 4000,
    queryFn: async () =>
      (await api.get<Order[]>("/api/orders", { params: { open_only: openOnly } })).data,
  });

export const useTrades = () =>
  useQuery({
    queryKey: ["trades"],
    queryFn: async () => (await api.get<Trade[]>("/api/orders/trades/book")).data,
  });

export const usePositions = () =>
  useQuery({
    queryKey: ["positions"],
    refetchInterval: 5000,
    queryFn: async () => (await api.get<Position[]>("/api/portfolio/positions")).data,
  });

export const useHoldings = () =>
  useQuery({
    queryKey: ["holdings"],
    refetchInterval: 5000,
    queryFn: async () => (await api.get<Holding[]>("/api/portfolio/holdings")).data,
  });

export function useInstrumentsByKey(keys: string[]) {
  return useQuery({
    queryKey: ["by-key", keys.join(",")],
    enabled: keys.length > 0,
    queryFn: async () =>
      (await api.get<Instrument[]>("/api/instruments/by-key", { params: { keys: keys.join(",") } }))
        .data,
  });
}

export const useUnderlyings = () =>
  useQuery({
    queryKey: ["underlyings"],
    queryFn: async () => (await api.get<Instrument[]>("/api/instruments/underlyings")).data,
  });

export function useOptionChain(underlyingKey: string | undefined) {
  return useQuery({
    queryKey: ["optionchain", underlyingKey],
    enabled: !!underlyingKey,
    refetchInterval: 5000,
    queryFn: async () =>
      (
        await api.get<OptionRow[]>("/api/instruments/option-chain", {
          params: { underlying_key: underlyingKey },
        })
      ).data,
  });
}

export function useCandles(instrumentKey: string | undefined, interval: string) {
  const intraday = interval === "1minute" || interval === "30minute";
  return useQuery({
    queryKey: ["candles", instrumentKey, interval],
    enabled: !!instrumentKey,
    // keep the chart current during the session — tighter for intraday intervals
    refetchInterval: intraday ? 20_000 : 60_000,
    queryFn: async () =>
      (
        await api.get<{ ts: string; open: string; high: string; low: string; close: string }[]>(
          `/api/instruments/${instrumentKey}/candles`,
          { params: { interval, days: interval === "1minute" ? 5 : 250 } },
        )
      ).data,
  });
}

export const usePnlReport = (from?: string, to?: string) =>
  useQuery({
    queryKey: ["report-pnl", from, to],
    queryFn: async () =>
      (await api.get("/api/reports/pnl", { params: { from_date: from, to_date: to } })).data,
  });

export const useChargesReport = (from?: string, to?: string) =>
  useQuery({
    queryKey: ["report-charges", from, to],
    queryFn: async () =>
      (await api.get("/api/reports/charges", { params: { from_date: from, to_date: to } })).data,
  });

export const useLeaderboard = () =>
  useQuery({
    queryKey: ["leaderboard"],
    refetchInterval: 15000,
    queryFn: async () => (await api.get("/api/leaderboard")).data,
  });

/* ---------- mutations ---------- */

const invalidatePortfolio = (qc: ReturnType<typeof useQueryClient>) => {
  ["funds", "ledger", "summary", "positions", "holdings", "orders", "trades", "leaderboard"].forEach(
    (k) => qc.invalidateQueries({ queryKey: [k] }),
  );
};

export function useResetAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post("/api/account/reset")).data,
    onSuccess: () => invalidatePortfolio(qc),
  });
}

export function useSquareOff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post("/api/portfolio/square-off")).data,
    onSuccess: () => invalidatePortfolio(qc),
  });
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PlaceOrderBody) => (await api.post<Order>("/api/orders", body)).data,
    onSuccess: () => invalidatePortfolio(qc),
  });
}

export function useCancelOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.delete(`/api/orders/${id}`)).data,
    onSuccess: () => invalidatePortfolio(qc),
  });
}

export function useAddWatchItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ wl, key }: { wl: number; key: string }) =>
      (await api.post(`/api/watchlists/${wl}/items`, { instrument_key: key })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
}

export function useRemoveWatchItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ wl, key }: { wl: number; key: string }) =>
      (await api.delete(`/api/watchlists/${wl}/items/${key}`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
}
