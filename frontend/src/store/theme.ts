import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Mode = "light" | "dark" | "system";
export type Pnl = "classic" | "colorblind";

export interface AccentPreset {
  key: string;
  name: string;
  accent: string; // "r g b"
  hover: string;
}

export const ACCENTS: AccentPreset[] = [
  { key: "indigo", name: "Indigo", accent: "79 70 229", hover: "67 56 202" },
  { key: "blue", name: "Blue", accent: "37 99 235", hover: "29 78 216" },
  { key: "violet", name: "Violet", accent: "124 58 237", hover: "109 40 217" },
  { key: "emerald", name: "Emerald", accent: "5 150 105", hover: "4 120 87" },
  { key: "teal", name: "Teal", accent: "13 148 136", hover: "15 118 110" },
  { key: "rose", name: "Rose", accent: "225 29 72", hover: "190 18 60" },
  { key: "amber", name: "Amber", accent: "217 119 6", hover: "180 83 9" },
  { key: "slate", name: "Slate", accent: "51 65 85", hover: "30 41 59" },
];

const PNL: Record<Pnl, { up: string; down: string }> = {
  classic: { up: "22 163 74", down: "220 38 38" },
  colorblind: { up: "37 99 235", down: "234 88 12" },
};

interface ThemeState {
  mode: Mode;
  accent: string;
  pnl: Pnl;
  setMode: (m: Mode) => void;
  setAccent: (k: string) => void;
  setPnl: (p: Pnl) => void;
  reset: () => void;
}

const DEFAULTS = { mode: "light" as Mode, accent: "indigo", pnl: "classic" as Pnl };

export const useTheme = create<ThemeState>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      setMode: (mode) => set({ mode }),
      setAccent: (accent) => set({ accent }),
      setPnl: (pnl) => set({ pnl }),
      reset: () => set(DEFAULTS),
    }),
    { name: "paper-trading-theme" },
  ),
);

/** Apply the current theme to <html>. Safe to call before React mounts. */
export function applyTheme(s: Pick<ThemeState, "mode" | "accent" | "pnl">) {
  const root = document.documentElement;

  const prefersDark =
    window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  const dark = s.mode === "dark" || (s.mode === "system" && prefersDark);
  root.setAttribute("data-theme", dark ? "dark" : "light");

  const a = ACCENTS.find((x) => x.key === s.accent) ?? ACCENTS[0];
  root.style.setProperty("--accent", a.accent);
  root.style.setProperty("--accent-hover", a.hover);

  const p = PNL[s.pnl] ?? PNL.classic;
  root.style.setProperty("--up", p.up);
  root.style.setProperty("--down", p.down);
}
