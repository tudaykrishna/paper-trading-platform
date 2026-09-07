import { create } from "zustand";
import type { Instrument } from "../api/hooks";

interface ChartFocusState {
  instrument: Instrument | null;
  set: (i: Instrument) => void;
}

/** Lets the watchlist rail (or anywhere) pick what the Chart page shows. */
export const useChartFocus = create<ChartFocusState>((set) => ({
  instrument: null,
  set: (instrument) => set({ instrument }),
}));
