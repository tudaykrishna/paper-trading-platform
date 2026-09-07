import { create } from "zustand";

export interface LiveQuote {
  instrument_key: string;
  ltp: number;
  prev_close?: number | null;
  open?: number | null;
  change?: number | null;
  change_pct?: number | null;
  ts?: string;
}

const pctOf = (ltp: number, prev?: number | null, open?: number | null): number | null => {
  const base = prev && prev > 0 ? prev : open && open > 0 ? open : null;
  return base == null ? null : ((ltp - base) / base) * 100;
};

interface QuoteState {
  quotes: Record<string, LiveQuote>;
  upsert: (q: LiveQuote) => void;
  seed: (
    qs: Record<
      string,
      {
        ltp: string;
        prev_close?: string | null;
        open?: string | null;
        change?: string | null;
        change_pct?: string | null;
      }
    >,
  ) => void;
}

export const useQuoteStore = create<QuoteState>((set) => ({
  quotes: {},
  upsert: (q) =>
    set((s) => {
      const merged = { ...s.quotes[q.instrument_key], ...q };
      merged.change_pct = pctOf(merged.ltp, merged.prev_close, merged.open);
      return { quotes: { ...s.quotes, [q.instrument_key]: merged } };
    }),
  seed: (qs) =>
    set((s) => {
      const next = { ...s.quotes };
      for (const [k, v] of Object.entries(qs)) {
        const ltp = Number(v.ltp);
        const prev = v.prev_close != null ? Number(v.prev_close) : null;
        const open = v.open != null ? Number(v.open) : null;
        next[k] = {
          instrument_key: k,
          ltp,
          prev_close: prev,
          open,
          change: v.change != null ? Number(v.change) : null,
          change_pct: v.change_pct != null ? Number(v.change_pct) : pctOf(ltp, prev, open),
        };
      }
      return { quotes: next };
    }),
}));
