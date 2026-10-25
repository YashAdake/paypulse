import { History } from "lucide-react";
import type { IncidentSummary } from "../api";
import { Card, Dot, Empty, Pill, type Tone } from "../components";
import { ago, seconds } from "../format";

const TEMPORAL_TONE: Record<string, Tone> = {
  RUNNING: "bad",
  COMPLETED: "good",
  FAILED: "warn",
  TERMINATED: "muted",
  CANCELED: "muted",
  TIMED_OUT: "warn",
};

export function IncidentList({
  incidents,
  selectedRunId,
  onSelect,
}: {
  incidents: IncidentSummary[] | undefined;
  selectedRunId: string | undefined;
  onSelect: (incident: IncidentSummary) => void;
}) {
  return (
    <Card title="Incidents" icon={<History className="h-4 w-4 text-violet-300" />}>
      {!incidents || incidents.length === 0 ? (
        <Empty>No incidents yet. Inject a fault to start one.</Empty>
      ) : (
        <ul className="max-h-80 space-y-2 overflow-y-auto pr-1">
          {incidents.map((inc) => {
            const tone = TEMPORAL_TONE[inc.temporal_status] ?? "muted";
            const active = inc.run_id === selectedRunId;
            return (
              <li key={inc.run_id}>
                <button
                  type="button"
                  onClick={() => onSelect(inc)}
                  className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                    active
                      ? "border-sky-500/60 bg-sky-500/10"
                      : "border-slate-800 bg-slate-900/40 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="flex items-center gap-2 text-sm font-semibold text-slate-100">
                      <Dot tone={tone} pulse={inc.temporal_status === "RUNNING"} />
                      {inc.bank} incident
                    </span>
                    <Pill tone={tone}>{inc.temporal_status.toLowerCase()}</Pill>
                  </div>
                  <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                    <span>opened {ago(inc.started_at)}</span>
                    <span>{inc.closed_at ? `took ${seconds(inc.started_at, inc.closed_at)}` : "in progress"}</span>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
