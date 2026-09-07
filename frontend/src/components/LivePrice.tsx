import { useQuoteStore } from "../store/quotes";
import { inr, pct, signClass } from "../lib/format";

/** Last price for an instrument: live from the WS store, else the passed fallback. */
export function useLtp(key: string, fallback?: string | number | null): number | null {
  const q = useQuoteStore((s) => s.quotes[key]);
  if (q?.ltp != null) return q.ltp;
  if (fallback != null && fallback !== "") return Number(fallback);
  return null;
}

export function LivePrice({
  instrumentKey,
  fallbackLtp,
  fallbackChangePct,
}: {
  instrumentKey: string;
  fallbackLtp?: string | null;
  fallbackChangePct?: string | null;
}) {
  const q = useQuoteStore((s) => s.quotes[instrumentKey]);
  const ltp = q?.ltp ?? (fallbackLtp != null ? Number(fallbackLtp) : null);
  const changePct =
    q?.change_pct ?? (fallbackChangePct != null ? Number(fallbackChangePct) : null);
  return (
    <span className="mono">
      <span className={`font-semibold ${changePct != null ? signClass(changePct) : ""}`}>
        {ltp == null ? "—" : inr(ltp)}
      </span>
      {changePct != null && (
        <span className={`ml-2 text-xs ${signClass(changePct)}`}>{pct(changePct)}</span>
      )}
    </span>
  );
}
