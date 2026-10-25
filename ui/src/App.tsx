import { HeartPulse } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type IncidentSummary } from "./api";
import { Card, Dot, Empty, Pill } from "./components";
import { DemoControls } from "./panels/DemoControls";
import { IncidentDetail } from "./panels/IncidentDetail";
import { IncidentList } from "./panels/IncidentList";
import { LivePayments } from "./panels/LivePayments";
import { PoweredBy } from "./panels/PoweredBy";
import { usePoll } from "./usePoll";

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);
  return <span className="font-mono text-sm text-slate-400">{now.toLocaleTimeString([], { hour12: false })}</span>;
}

export default function App() {
  const live = usePoll(api.live, 2000);
  const status = usePoll(api.status, 5000);
  const incidents = usePoll(api.incidents, 2000);

  // Follow the newest incident automatically; clicking an older one pins it until a new one opens.
  const [pinned, setPinned] = useState<IncidentSummary | null>(null);
  const newest = incidents.data?.incidents[0];
  const newestRunId = newest?.run_id;
  useEffect(() => {
    setPinned(null);
  }, [newestRunId]);
  const selected = pinned ?? newest;

  const activeCount = incidents.data?.incidents.filter((i) => i.temporal_status === "RUNNING").length ?? 0;

  return (
    <div className="mx-auto max-w-[1600px] space-y-4 px-4 py-5 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 p-2.5 shadow-lg shadow-sky-900/40">
            <HeartPulse className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">
              PayPulse <span className="font-medium text-slate-400">Command Center</span>
            </h1>
            <p className="text-xs text-slate-400">
              Finds why payments fail in seconds, remembers past fixes, repairs with one click.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {activeCount > 0 ? (
            <Pill tone="bad">
              <Dot tone="bad" pulse /> {activeCount} active incident{activeCount > 1 ? "s" : ""}
            </Pill>
          ) : (
            <Pill tone="good">
              <Dot tone="good" /> All payments healthy
            </Pill>
          )}
          <Clock />
        </div>
      </header>

      <PoweredBy partners={status.data?.partners} />

      <div className="grid gap-4 xl:grid-cols-4">
        <div className="xl:col-span-3">
          <LivePayments data={live.data} error={live.error} />
        </div>
        <div className="space-y-4">
          <DemoControls rules={live.data?.chaos.rules ?? []} onChange={live.refresh} />
          <IncidentList
            incidents={incidents.data?.incidents}
            selectedRunId={selected?.run_id}
            onSelect={setPinned}
          />
        </div>
      </div>

      {selected ? (
        // key: a different incident gets a fresh panel instead of flashing the old one's data.
        <IncidentDetail key={selected.run_id} workflowId={selected.workflow_id} runId={selected.run_id} />
      ) : (
        <Card title="Incident">
          <Empty>
            All quiet. Use <span className="font-semibold text-slate-300">Demo controls</span> to break a
            bank; PayPulse will open an incident within about 10 seconds.
          </Empty>
        </Card>
      )}

      <footer className="pb-4 text-center text-[11px] text-slate-600">
        Temporal · Supermemory · Jarvislabs · Kepler by RubixKube · Postgres · FastAPI · React
      </footer>
    </div>
  );
}
