import { useFunds, useLedger, useResetAccount, useSummary } from "../api/hooks";
import { inr, signClass } from "../lib/format";
import { fmtIST } from "../lib/time";

function Stat({ label, value, cls = "" }: { label: string; value: string; cls?: string }) {
  return (
    <div className="card p-5">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">{label}</div>
      <div className={`mono mt-2 text-[23px] font-semibold ${cls}`}>{value}</div>
    </div>
  );
}

export default function Dashboard() {
  const funds = useFunds();
  const summary = useSummary();
  const ledger = useLedger();
  const reset = useResetAccount();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-bold tracking-tight">Dashboard</h1>
        <button
          className="btn-ghost"
          disabled={reset.isPending}
          onClick={() => {
            if (
              confirm(
                "Reset account? All positions are flattened and cash returns to the opening balance.",
              )
            )
              reset.mutate();
          }}
        >
          {reset.isPending ? "Resetting…" : "Reset account"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Available cash" value={inr(funds.data?.available_cash)} />
        <Stat label="Blocked margin" value={inr(funds.data?.blocked_margin)} />
        <Stat
          label="Day P&L"
          value={inr(summary.data?.day_pnl)}
          cls={signClass(summary.data?.day_pnl)}
        />
        <Stat label="Holdings value" value={inr(summary.data?.holdings_value)} />
      </div>

      <section>
        <h2 className="mb-3 text-[15px] font-bold">Ledger</h2>
        <div className="card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Time</th>
                <th className="th">Type</th>
                <th className="th text-right">Amount</th>
                <th className="th text-right">Balance</th>
                <th className="th">Note</th>
              </tr>
            </thead>
            <tbody>
              {ledger.data?.length ? (
                ledger.data.map((e) => (
                  <tr key={e.id}>
                    <td className="td text-muted">{fmtIST(e.ts, "dd MMM, HH:mm:ss")}</td>
                    <td className="td">{e.type}</td>
                    <td className={`td mono text-right ${signClass(e.amount)}`}>{inr(e.amount)}</td>
                    <td className="td mono text-right">{inr(e.balance_after)}</td>
                    <td className="td text-muted">{e.note}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="td py-6 text-center text-faint" colSpan={5}>
                    No entries yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
