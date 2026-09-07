import { useChargesReport, usePnlReport } from "../api/hooks";
import { inr, signClass } from "../lib/format";

export default function Reports() {
  const pnl = usePnlReport();
  const charges = useChargesReport();
  const t = pnl.data?.totals;
  const heads = ["brokerage", "stt", "exchange_txn", "sebi", "stamp_duty", "gst"];

  return (
    <div className="space-y-6">
      <h1 className="text-[22px] font-bold tracking-tight">Reports</h1>

      {t && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat label="Realized P&L" value={inr(t.realized_pnl)} cls={signClass(t.realized_pnl)} big />
          <Stat label="Charges" value={inr(t.charges)} big />
          <Stat label="Net P&L" value={inr(t.net_pnl)} cls={signClass(t.net_pnl)} big />
          <Stat label="Turnover" value={inr(t.turnover)} big />
        </div>
      )}

      <section>
        <h2 className="mb-2 text-[14px] font-bold">By day</h2>
        <Table
          cols={["Date", "Realized", "Charges", "Turnover", "Trades"]}
          rows={(pnl.data?.by_day ?? []).map((d: any) => [
            d.date,
            <span className={`mono ${signClass(d.realized_pnl)}`}>{inr(d.realized_pnl)}</span>,
            <span className="mono">{inr(d.charges)}</span>,
            <span className="mono">{inr(d.turnover)}</span>,
            <span className="mono">{d.trades}</span>,
          ])}
        />
      </section>

      <section>
        <h2 className="mb-2 text-[14px] font-bold">By instrument</h2>
        <Table
          cols={["Instrument", "Realized", "Charges", "Trades"]}
          rows={(pnl.data?.by_instrument ?? []).map((d: any) => [
            <span className="font-semibold">{d.instrument_key}</span>,
            <span className={`mono ${signClass(d.realized_pnl)}`}>{inr(d.realized_pnl)}</span>,
            <span className="mono">{inr(d.charges)}</span>,
            <span className="mono">{d.trades}</span>,
          ])}
        />
      </section>

      <section>
        <h2 className="mb-2 text-[14px] font-bold">Charges breakdown</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {heads.map((h) => (
            <Stat key={h} label={h.replace("_", " ")} value={inr(charges.data?.breakdown?.[h] ?? 0)} />
          ))}
          <div className="card border-accent-line bg-accent-soft p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-accent">Total</div>
            <div className="mono mt-1 text-[15px] font-bold text-accent">
              {inr(charges.data?.total ?? 0)}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  cls = "",
  big = false,
}: {
  label: string;
  value: string;
  cls?: string;
  big?: boolean;
}) {
  return (
    <div className="card p-4">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">{label}</div>
      <div className={`mono mt-1 font-semibold ${big ? "text-[22px]" : "text-[15px]"} ${cls}`}>
        {value}
      </div>
    </div>
  );
}

function Table({ cols, rows }: { cols: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="card overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} className="th">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length ? (
            rows.map((r, i) => (
              <tr key={i}>
                {r.map((cell, j) => (
                  <td key={j} className="td">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={cols.length} className="td py-6 text-center text-faint">
                Nothing in range.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
