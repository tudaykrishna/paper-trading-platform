import { useState } from "react";
import { useCancelOrder, useOrders, useTrades } from "../api/hooks";
import { inr, num, signClass } from "../lib/format";
import { fmtIST } from "../lib/time";

const statusChip: Record<string, string> = {
  OPEN: "bg-amber-100 text-amber-700",
  COMPLETE: "bg-up/10 text-up",
  CANCELLED: "bg-surface-2 text-muted",
  REJECTED: "bg-down/10 text-down",
  PENDING: "bg-surface-2 text-muted",
};

export default function Orders() {
  const [tab, setTab] = useState<"orders" | "trades">("orders");
  const orders = useOrders();
  const trades = useTrades();
  const cancel = useCancelOrder();

  return (
    <div className="space-y-4">
      <h1 className="text-[22px] font-bold tracking-tight">Orders</h1>

      <div className="inline-flex gap-0.5 rounded-lg bg-surface-2 p-0.5">
        {(["orders", "trades"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-md px-3.5 py-1.5 text-[13px] font-medium ${
              tab === t ? "bg-surface font-semibold text-ink shadow-sm" : "text-muted"
            }`}
          >
            {t === "orders" ? "Order book" : "Trade book"}
          </button>
        ))}
      </div>

      {tab === "orders" ? (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Instrument</th>
                <th className="th">Side</th>
                <th className="th text-right">Qty</th>
                <th className="th">Type · Product</th>
                <th className="th text-right">Price</th>
                <th className="th">Status</th>
                <th className="th"></th>
              </tr>
            </thead>
            <tbody>
              {orders.data?.length ? (
                orders.data.map((o) => (
                  <tr key={o.id}>
                    <td className="td font-semibold">{o.instrument_key}</td>
                    <td className={`td font-bold ${o.side === "BUY" ? "text-up" : "text-down"}`}>
                      {o.side}
                    </td>
                    <td className="td mono text-right">
                      {o.filled_qty}/{o.qty}
                    </td>
                    <td className="td text-muted">
                      {o.order_type} · {o.product}
                    </td>
                    <td className="td mono text-right">
                      {o.order_type === "MARKET" ? "MKT" : num(o.price)}
                      {o.trigger_price && ` (t ${num(o.trigger_price)})`}
                    </td>
                    <td className="td">
                      <span
                        className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${statusChip[o.status]}`}
                      >
                        {o.status}
                      </span>
                      {o.reject_reason && <div className="text-[11px] text-down">{o.reject_reason}</div>}
                    </td>
                    <td className="td text-right">
                      {o.status === "OPEN" && (
                        <button
                          onClick={() => cancel.mutate(o.id)}
                          className="rounded-md border border-line px-2.5 py-1 text-xs hover:bg-surface-2"
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="td py-8 text-center text-faint" colSpan={7}>
                    No orders yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Time</th>
                <th className="th">Instrument</th>
                <th className="th">Side</th>
                <th className="th text-right">Qty</th>
                <th className="th text-right">Price</th>
                <th className="th text-right">Charges</th>
                <th className="th text-right">Net</th>
              </tr>
            </thead>
            <tbody>
              {trades.data?.length ? (
                trades.data.map((t) => (
                  <tr key={t.id}>
                    <td className="td text-muted">{fmtIST(t.ts, "HH:mm:ss")}</td>
                    <td className="td font-semibold">{t.instrument_key}</td>
                    <td className={`td font-bold ${t.side === "BUY" ? "text-up" : "text-down"}`}>
                      {t.side}
                    </td>
                    <td className="td mono text-right">{t.qty}</td>
                    <td className="td mono text-right">{num(t.price)}</td>
                    <td className="td mono text-right text-muted">{inr(t.charges)}</td>
                    <td className={`td mono text-right ${signClass(t.net_amount)}`}>
                      {inr(t.net_amount)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="td py-8 text-center text-faint" colSpan={7}>
                    No trades yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
