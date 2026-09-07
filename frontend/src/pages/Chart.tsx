import { useEffect, useRef, useState } from "react";
import { CandlestickData, createChart, IChartApi } from "lightweight-charts";
import { Instrument, useCandles, useQuotes } from "../api/hooks";
import { useMarketSocket } from "../api/ws";
import { useQuoteStore } from "../store/quotes";
import { useChartFocus } from "../store/chartFocus";
import { useOrderPad } from "../store/orderPad";
import InstrumentSearch from "../components/InstrumentSearch";
import { LivePrice } from "../components/LivePrice";
import { chartTime } from "../lib/time";
import { useTheme } from "../store/theme";

// CSS vars hold a space-separated triple ("148 163 184"); lightweight-charts
// needs a comma-separated rgb() string.
const cssRgb = (name: string) => {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v ? `rgb(${v.split(/\s+/).join(", ")})` : "#888888";
};

const INTERVALS = [
  ["1minute", "1m"],
  ["30minute", "30m"],
  ["day", "1D"],
  ["week", "1W"],
] as const;

export default function Chart() {
  const focused = useChartFocus((s) => s.instrument);
  const setFocus = useChartFocus((s) => s.set);
  const [inst, setInst] = useState<Instrument | null>(focused);
  const [interval, setInterval] = useState<string>("day");
  const openPad = useOrderPad((s) => s.open);
  const { data: candles } = useCandles(inst?.instrument_key, interval);

  useEffect(() => {
    if (focused && focused.instrument_key !== inst?.instrument_key) setInst(focused);
  }, [focused]); // eslint-disable-line react-hooks/exhaustive-deps

  const chartKeys = inst ? [inst.instrument_key] : [];
  useMarketSocket(chartKeys);
  useQuotes(chartKeys);
  const ltp = useQuoteStore((s) => (inst ? s.quotes[inst.instrument_key]?.ltp ?? null : null));
  const themeKey = useTheme((s) => `${s.mode}-${s.accent}-${s.pnl}`);

  const boxRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ReturnType<IChartApi["addCandlestickSeries"]> | null>(null);
  const lastBarRef = useRef<CandlestickData | null>(null);

  useEffect(() => {
    if (!boxRef.current) return;
    const grid = cssRgb("--line-soft");
    const border = cssRgb("--line");
    const up = cssRgb("--up");
    const down = cssRgb("--down");
    const accent = cssRgb("--accent");
    const chart = createChart(boxRef.current, {
      height: 440,
      layout: { background: { color: "transparent" }, textColor: cssRgb("--muted") },
      grid: { horzLines: { color: grid }, vertLines: { color: grid } },
      timeScale: {
        timeVisible: interval.includes("minute"),
        secondsVisible: false,
        borderColor: border,
      },
      rightPriceScale: { borderColor: border },
      crosshair: {
        horzLine: { labelBackgroundColor: accent },
        vertLine: { labelBackgroundColor: accent },
      },
    });
    chartRef.current = chart;
    seriesRef.current = chart.addCandlestickSeries({
      upColor: up,
      downColor: down,
      wickUpColor: up,
      wickDownColor: down,
      borderVisible: false,
    });
    const onResize = () =>
      boxRef.current && chart.applyOptions({ width: boxRef.current.clientWidth });
    onResize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
    };
  }, [interval, inst?.instrument_key, themeKey]);

  const daily = interval === "day" || interval === "week" || interval === "month";

  useEffect(() => {
    if (!seriesRef.current || !candles) return;
    const data: CandlestickData[] = candles.map((c) => ({
      time: chartTime(c.ts, daily),
      open: Number(c.open),
      high: Number(c.high),
      low: Number(c.low),
      close: Number(c.close),
    }));
    seriesRef.current.setData(data);
    lastBarRef.current = data[data.length - 1] ?? null;
    chartRef.current?.timeScale().fitContent();
  }, [candles, daily, themeKey]);

  useEffect(() => {
    if (ltp == null || !seriesRef.current || !lastBarRef.current) return;
    const b = lastBarRef.current;
    const updated: CandlestickData = {
      time: b.time,
      open: b.open,
      high: Math.max(b.high, ltp),
      low: Math.min(b.low, ltp),
      close: ltp,
    };
    lastBarRef.current = updated;
    seriesRef.current.update(updated);
  }, [ltp]);

  return (
    <div className="space-y-4">
      <div className="max-w-md">
        <InstrumentSearch
          defaultCategory=""
          onSelect={(i) => {
            setInst(i);
            setFocus(i);
          }}
          placeholder="Search to chart an instrument…"
        />
      </div>

      {inst ? (
        <div className="card p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[17px] font-semibold">
                {inst.tradingsymbol}{" "}
                <span className="text-xs font-medium text-faint">{inst.name}</span>
              </div>
              <div className="mt-1">
                <LivePrice instrumentKey={inst.instrument_key} />
              </div>
            </div>
            <div className="flex gap-1">
              {INTERVALS.map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setInterval(v)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium ${
                    interval === v ? "bg-accent text-white" : "bg-surface-2 text-muted"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                className="rounded-lg bg-up px-5 py-2 text-sm font-bold text-white"
                onClick={() => openPad(inst, "BUY")}
              >
                Buy
              </button>
              <button
                className="rounded-lg bg-down px-5 py-2 text-sm font-bold text-white"
                onClick={() => openPad(inst, "SELL")}
              >
                Sell
              </button>
            </div>
          </div>
          <div ref={boxRef} />
        </div>
      ) : (
        <p className="text-muted">Pick an instrument to see its chart — or click one in the watchlist.</p>
      )}
    </div>
  );
}
