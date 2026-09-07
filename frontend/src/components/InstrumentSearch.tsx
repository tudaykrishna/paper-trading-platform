import { useState } from "react";
import { Instrument, useInstrumentSearch } from "../api/hooks";

const CATEGORIES: [string, string][] = [
  ["", "All"],
  ["EQUITY", "Stocks"],
  ["ETF", "ETFs"],
  ["INDEX", "Index"],
  ["FUTURE", "Futures"],
  ["OPTION", "Options"],
  ["MUTUAL_FUND", "Mutual funds"],
  ["BOND", "Bonds"],
  ["REIT_INVIT", "REIT / InvIT"],
  ["COMMODITY", "Commodity"],
  ["CURRENCY", "Currency"],
  ["SME", "SME"],
];

const catLabel: Record<string, string> = Object.fromEntries(
  CATEGORIES.map(([v, l]) => [v, l]),
);

export default function InstrumentSearch({
  onSelect,
  placeholder = "Search instruments…",
  segment,
  defaultCategory = "EQUITY",
}: {
  onSelect: (i: Instrument) => void;
  placeholder?: string;
  segment?: string;
  defaultCategory?: string;
}) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState(defaultCategory);
  const { data, isFetching } = useInstrumentSearch(q, {
    segment,
    category: category || undefined,
  });

  return (
    <div className="relative">
      <div className="flex items-center gap-2 rounded-lg border border-line bg-surface px-3 py-2 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent-soft">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round">
          <circle cx="11" cy="11" r="7" />
          <path d="m21 21-4.3-4.3" />
        </svg>
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 200)}
          placeholder={placeholder}
          className="w-full bg-transparent text-sm outline-none placeholder:text-faint"
        />
      </div>
      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-line bg-surface shadow-lg">
          <div className="flex flex-wrap gap-1 border-b border-line-soft bg-surface-2 p-1.5">
            {CATEGORIES.map(([v, label]) => (
              <button
                key={v || "all"}
                onMouseDown={(e) => {
                  e.preventDefault();
                  setCategory(v);
                }}
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  category === v
                    ? "bg-accent text-white"
                    : "text-muted hover:bg-line"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="max-h-72 overflow-y-auto">
            {q.length < 1 && (
              <div className="px-3 py-2 text-xs text-faint">Type to search…</div>
            )}
            {q.length >= 1 && isFetching && (
              <div className="px-3 py-2 text-xs text-faint">Searching…</div>
            )}
            {q.length >= 1 && data?.length === 0 && !isFetching && (
              <div className="px-3 py-2 text-xs text-faint">No matches</div>
            )}
            {data?.map((i) => (
              <button
                key={i.instrument_key}
                onMouseDown={() => {
                  onSelect(i);
                  setQ("");
                  setOpen(false);
                }}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-surface-2"
              >
                <span className="min-w-0">
                  <span className="font-medium">{i.tradingsymbol}</span>
                  <span className="ml-2 truncate text-xs text-faint">{i.name}</span>
                </span>
                <span className="ml-2 shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
                  {catLabel[i.category] ?? i.category} · {i.exchange}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
