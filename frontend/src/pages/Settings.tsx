import { ACCENTS, Mode, Pnl, useTheme } from "../store/theme";
import { inr } from "../lib/format";

const MODES: [Mode, string][] = [
  ["light", "Light"],
  ["dark", "Dark"],
  ["system", "System"],
];

export default function Settings() {
  const { mode, accent, pnl, setMode, setAccent, setPnl, reset } = useTheme();

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[22px] font-bold tracking-tight">Settings</h1>
        <button className="btn-ghost" onClick={reset}>
          Reset to defaults
        </button>
      </div>

      {/* appearance */}
      <section className="card p-5">
        <h2 className="text-[13px] font-bold uppercase tracking-wide text-faint">Appearance</h2>

        <div className="mt-4 flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">Theme</div>
            <div className="text-xs text-muted">Dark mode is a first pass — most surfaces adapt.</div>
          </div>
          <div className="inline-flex gap-0.5 rounded-lg bg-surface-2 p-0.5">
            {MODES.map(([m, label]) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`rounded-md px-3 py-1.5 text-[13px] font-medium ${
                  mode === m ? "bg-surface font-semibold text-ink shadow-sm" : "text-muted"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-5">
          <div className="text-sm font-medium">Accent colour</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {ACCENTS.map((a) => (
              <button
                key={a.key}
                title={a.name}
                onClick={() => setAccent(a.key)}
                className={`h-9 w-9 rounded-full ring-offset-2 ring-offset-surface transition ${
                  accent === a.key ? "ring-2 ring-ink" : "hover:scale-105"
                }`}
                style={{ background: `rgb(${a.accent})` }}
              />
            ))}
          </div>
        </div>

        <div className="mt-5 flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">Profit / loss colours</div>
            <div className="text-xs text-muted">
              Colourblind swaps green/red for blue/orange.
            </div>
          </div>
          <div className="inline-flex gap-0.5 rounded-lg bg-surface-2 p-0.5">
            {(["classic", "colorblind"] as Pnl[]).map((p) => (
              <button
                key={p}
                onClick={() => setPnl(p)}
                className={`rounded-md px-3 py-1.5 text-[13px] font-medium capitalize ${
                  pnl === p ? "bg-surface font-semibold text-ink shadow-sm" : "text-muted"
                }`}
              >
                {p === "colorblind" ? "Colourblind" : "Classic"}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* preview */}
      <section className="card p-5">
        <h2 className="text-[13px] font-bold uppercase tracking-wide text-faint">Preview</h2>
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <div className="card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">
              Available cash
            </div>
            <div className="mono mt-2 text-[20px] font-semibold">{inr(964132.55)}</div>
          </div>
          <div className="card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">
              Day P&amp;L
            </div>
            <div className="mono mt-2 text-[20px] font-semibold text-up">{inr(4218.6)}</div>
          </div>
          <div className="card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-faint">
              Open loss
            </div>
            <div className="mono mt-2 text-[20px] font-semibold text-down">{inr(-1082.5)}</div>
          </div>
          <div className="flex items-center justify-center gap-2">
            <button className="btn-primary">Buy</button>
            <span className="pill pill-on">Filter</span>
          </div>
        </div>
      </section>
    </div>
  );
}
