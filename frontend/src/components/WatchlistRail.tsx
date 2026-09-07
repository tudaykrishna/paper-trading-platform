import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Instrument,
  useAddWatchItem,
  useQuotes,
  useRemoveWatchItem,
  useWatchlists,
} from "../api/hooks";
import { useMarketSocket } from "../api/ws";
import { useOrderPad } from "../store/orderPad";
import { useChartFocus } from "../store/chartFocus";
import { useQuoteStore } from "../store/quotes";
import InstrumentSearch from "./InstrumentSearch";
import { num, pct, signClass } from "../lib/format";
import { useQueryClient } from "@tanstack/react-query";

const FILTERS: [string, string][] = [
  ["", "All"],
  ["EQUITY", "Stocks"],
  ["INDEX", "Index"],
  ["FUTURE", "F&O"],
];

function Row({ inst, k }: { inst: Instrument | null; k: string }) {
  const q = useQuoteStore((s) => s.quotes[k]);
  const openPad = useOrderPad((s) => s.open);
  const setChart = useChartFocus((s) => s.set);
  const removeItem = useRemoveWatchItem();
  const { data: wls } = useWatchlists();
  const wlId = wls?.[0]?.id;
  const navigate = useNavigate();

  const chg = q?.change_pct ?? null;

  return (
    <div className="group flex items-center justify-between border-b border-line-soft px-3 py-2 hover:bg-surface-2">
      <button
        className="min-w-0 text-left"
        onClick={() => {
          if (inst) {
            setChart(inst);
            navigate("/chart");
          }
        }}
      >
        <div className="truncate text-[12.5px] font-semibold">{inst?.tradingsymbol ?? k}</div>
      </button>

      {/* price — hidden on hover to make room for actions */}
      <div className="text-right tnum group-hover:hidden">
        <span className={`mono text-[12px] font-semibold ${chg != null ? signClass(chg) : ""}`}>
          {q?.ltp != null ? num(q.ltp) : "—"}
        </span>
        {chg != null && (
          <span className={`mono ml-1.5 text-[10.5px] ${signClass(chg)}`}>{pct(chg)}</span>
        )}
      </div>

      {/* hover actions */}
      <div className="hidden gap-1 group-hover:flex">
        {inst && (
          <>
            <button
              className="grid h-[22px] w-[22px] place-items-center rounded-md bg-up/10 text-[11px] font-bold text-up hover:bg-up/20"
              onClick={() => openPad(inst, "BUY")}
            >
              B
            </button>
            <button
              className="grid h-[22px] w-[22px] place-items-center rounded-md bg-down/10 text-[11px] font-bold text-down hover:bg-down/20"
              onClick={() => openPad(inst, "SELL")}
            >
              S
            </button>
            <button
              className="grid h-[22px] w-[22px] place-items-center rounded-md text-muted hover:bg-line"
              title="Chart"
              onClick={() => {
                setChart(inst);
                navigate("/chart");
              }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <path d="M3 3v18h18" />
                <path d="m19 9-5 5-4-4-3 3" />
              </svg>
            </button>
          </>
        )}
        <button
          className="grid h-[22px] w-[22px] place-items-center rounded-md text-faint hover:bg-line"
          onClick={() => wlId && removeItem.mutate({ wl: wlId, key: k })}
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export default function WatchlistRail() {
  const { data: watchlists } = useWatchlists();
  const add = useAddWatchItem();
  const qc = useQueryClient();
  const [tab, setTab] = useState(0);
  const [filter, setFilter] = useState("EQUITY");

  const wl = watchlists?.[tab] ?? watchlists?.[0];
  const items = wl?.items ?? [];
  const keys = useMemo(() => items.map((i) => i.instrument_key), [items]);

  // the rail is the app's live-price engine
  useMarketSocket(keys);
  useQuotes(keys);

  useEffect(() => {
    if (watchlists && tab >= watchlists.length) setTab(0);
  }, [watchlists, tab]);

  const shown = filter
    ? items.filter((i) => i.instrument?.category === filter || !i.instrument)
    : items;

  async function newList() {
    const name = prompt("Name the new list");
    if (!name) return;
    await api.post("/api/watchlists", { name });
    qc.invalidateQueries({ queryKey: ["watchlists"] });
    setTab((watchlists?.length ?? 1));
  }

  return (
    <div className="flex h-full w-[300px] flex-shrink-0 flex-col border-r border-line bg-surface">
      {/* list tabs */}
      <div className="flex items-center gap-0.5 border-b border-line-soft px-2 pt-1.5">
        {(watchlists ?? []).map((w, i) => (
          <button
            key={w.id}
            onClick={() => setTab(i)}
            className={`px-2.5 py-2 text-xs font-medium ${
              i === tab
                ? "border-b-2 border-accent font-semibold text-accent"
                : "text-muted hover:text-ink"
            }`}
          >
            {w.name}
          </button>
        ))}
        <button
          onClick={newList}
          className="ml-auto grid h-6 w-6 place-items-center rounded-md border border-line text-faint hover:bg-surface-2"
          title="New list"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      </div>

      {/* search + add */}
      <div className="px-2.5 pb-1.5 pt-2.5">
        <InstrumentSearch
          placeholder="Search & add…"
          onSelect={(inst) => wl && add.mutate({ wl: wl.id, key: inst.instrument_key })}
        />
      </div>

      {/* filter pills */}
      <div className="flex gap-1.5 overflow-hidden px-2.5 pb-2">
        {FILTERS.map(([v, label]) => (
          <button
            key={v || "all"}
            onClick={() => setFilter(v)}
            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${
              filter === v ? "border-accent-line bg-accent-soft text-accent" : "border-line text-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* list */}
      <div className="min-h-0 flex-1 overflow-y-auto border-t border-line-soft">
        {shown.length ? (
          shown.map((it) => <Row key={it.id} inst={it.instrument} k={it.instrument_key} />)
        ) : items.length ? (
          <p className="px-4 py-8 text-center text-xs text-faint">No matches for this filter.</p>
        ) : (
          <div className="px-4 py-8 text-center">
            <p className="text-xs text-faint">This list is empty.</p>
            <button
              className="mt-3 rounded-lg border border-accent-line bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent"
              onClick={async () => {
                await api.post("/api/watchlists/seed-popular");
                qc.invalidateQueries({ queryKey: ["watchlists"] });
              }}
            >
              Load popular list
            </button>
          </div>
        )}
      </div>

      <div className="border-t border-line-soft px-3 py-2 text-[11px] text-faint">
        {wl?.name ?? "List"} · {items.length} / 50
      </div>
    </div>
  );
}
