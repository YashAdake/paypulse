import { Activity, Zap } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { BANKS, METHODS, type LiveData, type StatsGroup } from "../api";
import { Card, Empty, Pill } from "../components";
import { clock, health, ms, pct } from "../format";

const BANK_COLORS: Record<string, string> = {
  HDFC: "#f43f5e",
  SBI: "#38bdf8",
  ICICI: "#a78bfa",
  AXIS: "#34d399",
};

type ChartRow = { time: string } & Record<string, number | string>;

function toChartRows(data: LiveData): ChartRow[] {
  // One row per time bucket, one column per bank, success rate as 0-100.
  const rows = new Map<string, ChartRow>();
  for (const point of data.timeseries.points) {
    const row = rows.get(point.bucket_start) ?? { time: clock(point.bucket_start) };
    row[point.bank] = Math.round(point.success_rate * 1000) / 10;
    rows.set(point.bucket_start, row);
  }
  return [...rows.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([, row]) => row);
}

const TILE_TONE = {
  good: "border-emerald-500/20 bg-emerald-500/5",
  warn: "border-amber-500/40 bg-amber-500/10",
  bad: "border-rose-500/60 bg-rose-500/10 shadow-lg shadow-rose-900/30",
  none: "border-slate-800 bg-slate-900/40",
};
const RATE_TONE = {
  good: "text-emerald-300",
  warn: "text-amber-300",
  bad: "text-rose-400",
  none: "text-slate-500",
};

function Tile({ bank, method, group }: { bank: string; method: string; group?: StatsGroup }) {
  const tone = health(group?.success_rate);
  return (
    <div className={`rounded-xl border p-3 transition-colors duration-500 ${TILE_TONE[tone]}`}>
      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-400">
        <span>
          {bank} · {method}
        </span>
        <span>{group ? `${group.total} tx` : "no traffic"}</span>
      </div>
      <div className={`mt-1 font-mono text-2xl font-semibold ${RATE_TONE[tone]}`}>
        {pct(group?.success_rate)}
      </div>
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-400">
        <span>p95 {ms(group?.p95_latency_ms)}</span>
        <span className="truncate pl-2 font-mono">{group?.top_error_code ?? "—"}</span>
      </div>
    </div>
  );
}

export function LivePayments({ data, error }: { data: LiveData | null; error: string | null }) {
  const faulty = new Set(data?.chaos.rules.map((r) => r.bank) ?? []);
  const rows = data ? toChartRows(data) : [];

  return (
    <Card
      title="Live payments"
      icon={<Activity className="h-4 w-4 text-sky-300" />}
      badge={<span className="text-xs font-normal text-slate-500">success rate · last 60 s</span>}
      actions={error ? <Pill tone="bad">{error}</Pill> : <Pill tone="good">streaming</Pill>}
    >
      <div className="h-56">
        {rows.length === 0 ? (
          <Empty>Waiting for traffic…</Empty>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={11} minTickGap={40} />
              <YAxis domain={[0, 100]} stroke="#64748b" fontSize={11} tickFormatter={(v) => `${v}%`} />
              <Tooltip
                contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 12 }}
                labelStyle={{ color: "#cbd5e1" }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine
                y={90}
                stroke="#f59e0b"
                strokeDasharray="6 4"
                label={{ value: "alert threshold 90%", fill: "#f59e0b", fontSize: 10, position: "insideBottomRight" }}
              />
              {BANKS.map((bank) => (
                <Line
                  key={bank}
                  type="monotone"
                  dataKey={bank}
                  stroke={BANK_COLORS[bank]}
                  strokeWidth={bank === "HDFC" ? 2.5 : 1.75}
                  dot={false}
                  unit="%"
                  isAnimationActive={false}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {BANKS.map((bank) => (
          <div key={bank} className="space-y-2">
            <div className="flex items-center justify-between px-1">
              <span className="text-xs font-semibold text-slate-300" style={{ color: BANK_COLORS[bank] }}>
                {bank}
              </span>
              {faulty.has(bank) && (
                <span className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-amber-300">
                  <Zap className="h-3 w-3" /> fault injected
                </span>
              )}
            </div>
            {METHODS.map((method) => (
              <Tile
                key={method}
                bank={bank}
                method={method}
                group={data?.stats.groups.find((g) => g.bank === bank && g.method === method)}
              />
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}
