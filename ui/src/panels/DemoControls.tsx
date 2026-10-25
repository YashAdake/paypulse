import { RotateCcw, Zap } from "lucide-react";
import { useState } from "react";
import { api, BANKS, type Bank, type ChaosRule } from "../api";
import { Card, ErrorNote } from "../components";
import { pct } from "../format";

export function DemoControls({ rules, onChange }: { rules: ChaosRule[]; onChange: () => void }) {
  const [bank, setBank] = useState<Bank>("HDFC");
  const [type, setType] = useState<"timeout" | "decline">("timeout");
  const [rate, setRate] = useState(0.6);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const select =
    "rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-200 focus:border-sky-500 focus:outline-none";

  return (
    <Card title="Demo controls" icon={<Zap className="h-4 w-4 text-amber-300" />}>
      <p className="mb-3 text-xs text-slate-400">
        Break a bank on purpose and watch PayPulse detect, explain and fix it.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <select className={select} value={bank} onChange={(e) => setBank(e.target.value as Bank)}>
          {BANKS.map((b) => (
            <option key={b}>{b}</option>
          ))}
        </select>
        <select
          className={select}
          value={type}
          onChange={(e) => setType(e.target.value as "timeout" | "decline")}
        >
          <option value="timeout">timeouts</option>
          <option value="decline">declines</option>
        </select>
      </div>
      <label className="mt-3 flex items-center gap-3 text-xs text-slate-400">
        <span className="w-16">Failure rate</span>
        <input
          type="range"
          min={0.1}
          max={1}
          step={0.1}
          value={rate}
          onChange={(e) => setRate(Number(e.target.value))}
          className="flex-1 accent-rose-500"
        />
        <span className="w-10 text-right font-mono text-slate-200">{pct(rate, 0)}</span>
      </label>
      <div className="mt-4 grid grid-cols-2 gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => run(() => api.injectChaos(bank, type, rate))}
          className="flex items-center justify-center gap-2 rounded-lg bg-rose-600 px-3 py-2 text-sm font-semibold text-white hover:bg-rose-500 disabled:opacity-50"
        >
          <Zap className="h-4 w-4" /> Inject fault
        </button>
        <button
          type="button"
          disabled={busy || rules.length === 0}
          onClick={() => run(() => api.clearChaos())}
          className="flex items-center justify-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-40"
        >
          <RotateCcw className="h-4 w-4" /> Clear all
        </button>
      </div>
      {rules.length > 0 && (
        <ul className="mt-4 space-y-1 text-xs text-slate-400">
          {rules.map((r) => (
            <li key={r.bank} className="flex justify-between rounded-md bg-slate-800/50 px-2 py-1">
              <span className="font-semibold text-amber-300">{r.bank}</span>
              <span>
                {pct(r.rate, 0)} {r.type}s
              </span>
            </li>
          ))}
        </ul>
      )}
      <ErrorNote message={error} />
    </Card>
  );
}
