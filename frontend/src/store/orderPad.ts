import { create } from "zustand";
import type { Instrument } from "../api/hooks";

interface OrderPadState {
  instrument: Instrument | null;
  side: "BUY" | "SELL";
  open: (instrument: Instrument, side?: "BUY" | "SELL") => void;
  close: () => void;
}

/** One order pad, mounted once in Layout, opened from anywhere. */
export const useOrderPad = create<OrderPadState>((set) => ({
  instrument: null,
  side: "BUY",
  open: (instrument, side = "BUY") => set({ instrument, side }),
  close: () => set({ instrument: null }),
}));
