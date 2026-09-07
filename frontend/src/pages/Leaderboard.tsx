import { useLeaderboard, useMe } from "../api/hooks";
import { inr, pct, signClass } from "../lib/format";

export default function Leaderboard() {
  const { data } = useLeaderboard();
  const { data: me } = useMe();

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-[22px] font-bold tracking-tight">Leaderboard</h1>
        <p className="mt-1 text-[13px] text-faint">
          Ranked by net worth vs the ₹10,00,000 opening balance.
        </p>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              <th className="th w-14">#</th>
              <th className="th">Trader</th>
              <th className="th text-right">Net worth</th>
              <th className="th text-right">P&amp;L</th>
              <th className="th text-right">Return</th>
            </tr>
          </thead>
          <tbody>
            {data?.rows?.length ? (
              data.rows.map((r: any) => (
                <tr key={r.user_id} className={r.user_id === me?.id ? "bg-accent-soft/60" : ""}>
                  <td className="td mono font-semibold text-faint">{r.rank}</td>
                  <td className="td font-semibold">
                    {r.name}
                    {r.user_id === me?.id && (
                      <span className="ml-1.5 rounded bg-accent-soft px-1.5 py-0.5 text-[11px] font-semibold text-accent">
                        you
                      </span>
                    )}
                  </td>
                  <td className="td mono text-right">{inr(r.net_worth)}</td>
                  <td className={`td mono text-right ${signClass(r.pnl)}`}>{inr(r.pnl)}</td>
                  <td className={`td mono text-right ${signClass(r.return_pct)}`}>{pct(r.return_pct)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="td py-8 text-center text-faint">
                  No traders yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
