import { useEffect, useMemo, useState } from "react";
import { useInstrumentsByKey, useOptionChain, useUnderlyings } from "../api/hooks";
import { useMarketSocket } from "../api/ws";
import { useQuotes } from "../api/hooks";
import { useOrderPad } from "../store/orderPad";
import { num } from "../lib/format";

export default function OptionChain() {
  const { data: underlyings } = useUnderlyings();
  const [underlying, setUnderlying] = useState<string>("");
  const openPad = useOrderPad((s) => s.open);

  useEffect(() => {
    if (!underlying && underlyings?.length) setUnderlying(underlyings[0].underlying_key ?? "");
  }, [underlyings, underlying]);

  const { data: chain } = useOptionChain(underlying || undefined);
  const optionKeys = useMemo(
    () => (chain ?? []).flatMap((r) => [r.call_key, r.put_key].filter(Boolean) as string[]),
    [chain],
  );
  const allKeys = useMemo(
    () => [underlying, ...optionKeys].filter(Boolean),
    [underlying, optionKeys],
  );
  useMarketSocket(allKeys);
  useQuotes(allKeys);

  const { data: instruments } = useInstrumentsByKey(optionKeys);
  const instByKey = useMemo(
    () => Object.fromEntries((instruments ?? []).map((i) => [i.instrument_key, i])),
    [instruments],
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-[22px] font-bold tracking-tight">Option chain</h1>
        <select
          value={underlying}
          onChange={(e) => setUnderlying(e.target.value)}
          className="rounded-lg border border-line bg-surface px-3 py-1.5 text-sm font-semibold"
        >
          {underlyings?.map((u) => (
            <option key={u.underlying_key ?? u.instrument_key} value={u.underlying_key ?? ""}>
              {u.tradingsymbol}
            </option>
          ))}
        </select>
        {chain?.[0] && (
          <span className="text-sm text-faint">
            Expiry <span className="font-medium text-muted">{chain[0].expiry}</span>
          </span>
        )}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th text-right">Call OI</th>
              <th className="th text-right">Call LTP</th>
              <th className="th bg-surface-2 text-center">Strike</th>
              <th className="th text-left">Put LTP</th>
              <th className="th text-left">Put OI</th>
            </tr>
          </thead>
          <tbody>
            {chain?.map((r) => {
              const ceInst = r.call_key ? instByKey[r.call_key] : undefined;
              const peInst = r.put_key ? instByKey[r.put_key] : undefined;
              return (
                <tr key={r.strike}>
                  <td className="td mono text-right text-faint">{r.call_oi}</td>
                  <td className="td text-right">
                    <button
                      className="mono rounded px-2 py-0.5 font-semibold text-up hover:bg-up/10"
                      onClick={() => ceInst && openPad(ceInst, "BUY")}
                    >
                      {num(r.call_ltp)}
                    </button>
                  </td>
                  <td className="td mono bg-surface-2 text-center font-bold">{num(r.strike, 0)}</td>
                  <td className="td text-left">
                    <button
                      className="mono rounded px-2 py-0.5 font-semibold text-down hover:bg-down/10"
                      onClick={() => peInst && openPad(peInst, "BUY")}
                    >
                      {num(r.put_ltp)}
                    </button>
                  </td>
                  <td className="td mono text-left text-faint">{r.put_oi}</td>
                </tr>
              );
            })}
            {!chain?.length && (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-faint">
                  No option chain available (needs an F&amp;O-enabled provider).
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-faint">Tap any LTP to open the order pad for that contract.</p>
    </div>
  );
}
