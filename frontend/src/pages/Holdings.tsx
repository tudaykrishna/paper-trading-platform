import { useMemo } from "react";
import { Holding, Instrument, useHoldings, useInstrumentsByKey, useQuotes } from "../api/hooks";
import { useMarketSocket } from "../api/ws";
import { useLtp } from "../components/LivePrice";
import { useOrderPad } from "../store/orderPad";
import { inr, num, signClass } from "../lib/format";

function Row({ h, inst }: { h: Holding; inst?: Instrument }) {
  const ltp = useLtp(h.instrument_key, h.ltp);
  const openPad = useOrderPad((s) => s.open);
  const value = ltp != null ? ltp * h.qty : Number(h.current_value ?? 0);
  const unreal = ltp != null ? (ltp - Number(h.avg_price)) * h.qty : Number(h.unrealized_pnl ?? 0);
  const pctChg = Number(h.avg_price) ? (unreal / (Number(h.avg_price) * h.qty)) * 100 : 0;
  return (
    <tr className="group">
      <td className="td font-semibold">{inst?.tradingsymbol ?? h.instrument_key}</td>
      <td className="td mono text-right">
        {h.qty}
        {h.settled_qty < h.qty && (
          <span className="ml-1 text-[11px] text-amber-600">({h.settled_qty} settled)</span>
        )}
      </td>
      <td className="td mono text-right">{num(h.avg_price)}</td>
      <td className="td mono text-right">{ltp == null ? "—" : num(ltp)}</td>
      <td className="td mono text-right">{inr(value)}</td>
      <td className={`td mono text-right ${signClass(unreal)}`}>
        {inr(unreal)}{" "}
        <span className="text-[11px]">
          ({pctChg >= 0 ? "+" : ""}
          {pctChg.toFixed(2)}%)
        </span>
      </td>
      <td className="td text-right">
        {inst && (
          <span className="inline-flex gap-1.5">
            <button
              className="rounded-md bg-up/10 px-2.5 py-1 text-xs font-bold text-up hover:bg-up/20"
              onClick={() => openPad(inst, "BUY")}
            >
              Buy
            </button>
            <button
              className="rounded-md bg-down/10 px-2.5 py-1 text-xs font-bold text-down hover:bg-down/20"
              onClick={() => openPad(inst, "SELL")}
            >
              Sell
            </button>
          </span>
        )}
      </td>
    </tr>
  );
}

export default function Holdings() {
  const { data } = useHoldings();
  const keys = useMemo(() => data?.map((h) => h.instrument_key) ?? [], [data]);
  useMarketSocket(keys);
  useQuotes(keys);
  const { data: instruments } = useInstrumentsByKey(keys);
  const byKey = useMemo(
    () => Object.fromEntries((instruments ?? []).map((i) => [i.instrument_key, i])),
    [instruments],
  );

  return (
    <div className="space-y-4">
      <h1 className="text-[22px] font-bold tracking-tight">Holdings</h1>
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">Instrument</th>
              <th className="th text-right">Qty</th>
              <th className="th text-right">Avg</th>
              <th className="th text-right">LTP</th>
              <th className="th text-right">Value</th>
              <th className="th text-right">P&amp;L</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody>
            {data?.length ? (
              data.map((h) => <Row key={h.instrument_key} h={h} inst={byKey[h.instrument_key]} />)
            ) : (
              <tr>
                <td className="td py-8 text-center text-faint" colSpan={7}>
                  No holdings. Buy a stock with product CNC to start investing.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
