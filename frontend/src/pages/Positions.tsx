import { useMemo } from "react";
import {
  Instrument,
  Position,
  useInstrumentsByKey,
  usePositions,
  useQuotes,
  useSquareOff,
} from "../api/hooks";
import { useMarketSocket } from "../api/ws";
import { useLtp } from "../components/LivePrice";
import { useOrderPad } from "../store/orderPad";
import { inr, num, signClass } from "../lib/format";

function Row({ p, inst }: { p: Position; inst?: Instrument }) {
  const ltp = useLtp(p.instrument_key, p.ltp);
  const openPad = useOrderPad((s) => s.open);
  const unreal =
    ltp != null && p.net_qty !== 0
      ? (ltp - Number(p.avg_price)) * p.net_qty
      : Number(p.unrealized_pnl ?? 0);
  return (
    <tr>
      <td className="td font-semibold">{inst?.tradingsymbol ?? p.instrument_key}</td>
      <td className="td text-muted">{p.product}</td>
      <td className={`td mono text-right ${signClass(p.net_qty)}`}>
        {p.net_qty > 0 ? `+${p.net_qty}` : p.net_qty}
      </td>
      <td className="td mono text-right">{num(p.avg_price)}</td>
      <td className="td mono text-right">{ltp == null ? "—" : num(ltp)}</td>
      <td className={`td mono text-right ${signClass(unreal)}`}>{inr(unreal)}</td>
      <td className={`td mono text-right ${signClass(p.realized_pnl)}`}>{inr(p.realized_pnl)}</td>
      <td className="td text-right">
        {inst && p.net_qty !== 0 && (
          <button
            className="rounded-md border border-line px-2.5 py-1 text-xs font-medium hover:bg-surface-2"
            onClick={() => openPad(inst, p.net_qty > 0 ? "SELL" : "BUY")}
          >
            {p.net_qty > 0 ? "Exit" : "Cover"}
          </button>
        )}
      </td>
    </tr>
  );
}

export default function Positions() {
  const { data } = usePositions();
  const squareOff = useSquareOff();
  const keys = useMemo(() => data?.map((p) => p.instrument_key) ?? [], [data]);
  useMarketSocket(keys);
  useQuotes(keys);
  const { data: instruments } = useInstrumentsByKey(keys);
  const byKey = useMemo(
    () => Object.fromEntries((instruments ?? []).map((i) => [i.instrument_key, i])),
    [instruments],
  );

  const open = data?.filter((p) => p.net_qty !== 0) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-bold tracking-tight">Positions</h1>
        {open.some((p) => p.product === "MIS") && (
          <button
            className="btn-ghost"
            disabled={squareOff.isPending}
            onClick={() => squareOff.mutate()}
          >
            {squareOff.isPending ? "Squaring off…" : "Square off MIS"}
          </button>
        )}
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th">Instrument</th>
              <th className="th">Product</th>
              <th className="th text-right">Net qty</th>
              <th className="th text-right">Avg</th>
              <th className="th text-right">LTP</th>
              <th className="th text-right">Unrealized</th>
              <th className="th text-right">Realized</th>
              <th className="th"></th>
            </tr>
          </thead>
          <tbody>
            {data?.length ? (
              data.map((p) => (
                <Row
                  key={`${p.instrument_key}-${p.product}`}
                  p={p}
                  inst={byKey[p.instrument_key]}
                />
              ))
            ) : (
              <tr>
                <td className="td py-8 text-center text-faint" colSpan={8}>
                  No open positions today.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
