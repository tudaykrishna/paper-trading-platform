import { useMemo, useState } from "react";
import { Instrument, usePlaceOrder } from "../api/hooks";
import { apiError } from "../api/client";
import { useOrderPad } from "../store/orderPad";
import { useLtp } from "./LivePrice";
import { inr } from "../lib/format";

const PRODUCTS: Record<string, string[]> = {
  EQ: ["CNC", "MIS"],
  FO: ["NRML", "MIS"],
  CDS: ["NRML", "MIS"],
  MCX: ["NRML", "MIS"],
};

/** Mounted once in Layout; opened from anywhere via useOrderPad().open(). */
export default function OrderPad() {
  const { instrument, side } = useOrderPad();
  if (!instrument) return null;
  return <Pad key={instrument.instrument_key} instrument={instrument} defaultSide={side} />;
}

function Pad({
  instrument,
  defaultSide,
}: {
  instrument: Instrument;
  defaultSide: "BUY" | "SELL";
}) {
  const close = useOrderPad((s) => s.close);
  const place = usePlaceOrder();
  const ltp = useLtp(instrument.instrument_key);
  const [side, setSide] = useState<"BUY" | "SELL">(defaultSide);
  const products = PRODUCTS[instrument.segment] ?? ["MIS"];
  const [product, setProduct] = useState(products[0]);
  const [orderType, setOrderType] = useState("MARKET");
  const [lots, setLots] = useState(1);
  const [price, setPrice] = useState("");
  const [trigger, setTrigger] = useState("");
  const [error, setError] = useState<string | null>(null);

  const qty = lots * instrument.lot_size;
  const needsLimit = orderType === "LIMIT" || orderType === "SL";
  const needsTrigger = orderType === "SL" || orderType === "SL-M";
  const est = useMemo(() => (needsLimit ? Number(price) : ltp ?? 0) * qty, [needsLimit, price, ltp, qty]);

  async function submit() {
    setError(null);
    try {
      await place.mutateAsync({
        instrument_key: instrument.instrument_key,
        side,
        qty,
        product,
        order_type: orderType,
        price: needsLimit ? price : undefined,
        trigger_price: needsTrigger ? trigger : undefined,
      });
      close();
    } catch (e) {
      setError(apiError(e));
    }
  }

  const field =
    "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4"
      onClick={close}
    >
      <div
        className="w-full max-w-[420px] overflow-hidden rounded-2xl bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between px-6 pt-5">
          <div>
            <div className="text-[17px] font-semibold">{instrument.tradingsymbol}</div>
            <div className="mt-0.5 text-xs text-faint">
              {instrument.name} · LTP <span className="mono">{ltp == null ? "—" : inr(ltp)}</span>
            </div>
          </div>
          <button onClick={close} className="text-faint hover:text-ink">
            ✕
          </button>
        </div>

        <div className="px-6 pb-6 pt-4">
          <div className="mb-4 grid grid-cols-2 gap-2">
            {(["BUY", "SELL"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSide(s)}
                className={`rounded-lg py-2 text-sm font-bold transition ${
                  side === s
                    ? s === "BUY"
                      ? "bg-up text-white"
                      : "bg-down text-white"
                    : "bg-surface-2 text-muted"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="space-y-3 text-sm">
            <div>
              <div className="mb-1.5 text-muted">
                Quantity <span className="text-faint">({instrument.lot_size} / lot)</span>
              </div>
              <div className="flex items-center gap-2.5">
                <input
                  type="number"
                  min={1}
                  value={lots}
                  onChange={(e) => setLots(Math.max(1, Number(e.target.value)))}
                  className={`${field} mono w-24`}
                />
                <span className="text-faint">= {qty} units</span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <label className="block">
                <div className="mb-1.5 text-muted">Product</div>
                <select
                  value={product}
                  onChange={(e) => setProduct(e.target.value)}
                  className={field}
                >
                  {products.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <div className="mb-1.5 text-muted">Type</div>
                <select
                  value={orderType}
                  onChange={(e) => setOrderType(e.target.value)}
                  className={field}
                >
                  {["MARKET", "LIMIT", "SL", "SL-M"].map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </label>
            </div>

            {needsLimit && (
              <label className="block">
                <div className="mb-1.5 text-muted">Limit price</div>
                <input
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  className={`${field} mono`}
                  placeholder={ltp ? String(ltp) : "0.00"}
                />
              </label>
            )}
            {needsTrigger && (
              <label className="block">
                <div className="mb-1.5 text-muted">Trigger price</div>
                <input
                  value={trigger}
                  onChange={(e) => setTrigger(e.target.value)}
                  className={`${field} mono`}
                  placeholder="0.00"
                />
              </label>
            )}

            <div className="flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2.5 text-xs text-muted">
              <span>Approx order value</span>
              <span className="mono font-semibold text-ink">{inr(est)}</span>
            </div>

            {error && <p className="text-sm text-down">{error}</p>}

            <button
              onClick={submit}
              disabled={place.isPending}
              className={`w-full rounded-xl py-3 text-sm font-bold text-white disabled:opacity-50 ${
                side === "BUY" ? "bg-up" : "bg-down"
              }`}
            >
              {place.isPending ? "Placing…" : `${side} ${instrument.tradingsymbol}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
