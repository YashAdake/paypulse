import {
  Brain,
  CircleCheck,
  CircleDashed,
  CircleMinus,
  CirclePause,
  CircleX,
  Database,
  ExternalLink,
  Gauge,
  HeartPulse,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
  Workflow,
} from "lucide-react";
import { useState } from "react";
import { api, type IncidentStatus, type Progress, type Step, type StepStatus } from "../api";
import { Card, Empty, ErrorNote, PartnerBadge, Pill, partnerKeyForTech, type Tone } from "../components";
import { clock, ms, pct, seconds, temporalUiUrl } from "../format";
import { usePoll } from "../usePoll";

const INCIDENT_TONE: Record<IncidentStatus, { tone: Tone; label: string }> = {
  investigating: { tone: "info", label: "Investigating" },
  awaiting_approval: { tone: "warn", label: "Awaiting approval" },
  remediating: { tone: "info", label: "Fixing" },
  resolved: { tone: "good", label: "Resolved" },
  unresolved: { tone: "bad", label: "Not recovered" },
  rejected: { tone: "muted", label: "Fix rejected" },
  expired: { tone: "muted", label: "Approval expired" },
  escalated: { tone: "warn", label: "Escalated" },
  failed: { tone: "bad", label: "Investigation failed" },
};

function StepIcon({ status }: { status: StepStatus }) {
  const cls = "h-5 w-5";
  switch (status) {
    case "done":
      return <CircleCheck className={`${cls} text-emerald-400`} />;
    case "running":
      return <LoaderCircle className={`${cls} animate-spin text-sky-400`} />;
    case "waiting":
      return <CirclePause className={`${cls} animate-pulse text-amber-400`} />;
    case "failed":
      return <CircleX className={`${cls} text-rose-400`} />;
    case "skipped":
      return <CircleMinus className={`${cls} text-slate-600`} />;
    default:
      return <CircleDashed className={`${cls} text-slate-600`} />;
  }
}

function Timeline({ steps }: { steps: Step[] }) {
  return (
    <ol className="relative space-y-1">
      {steps.map((step, i) => {
        const partner = partnerKeyForTech(step.tech);
        const live = step.status === "running" || step.status === "waiting";
        return (
          <li key={step.key} className="relative flex gap-3 pb-3">
            {i < steps.length - 1 && (
              <span className="absolute top-6 left-[9px] h-full w-px bg-slate-800" aria-hidden />
            )}
            <div className="z-10 bg-slate-900">
              <StepIcon status={step.status} />
            </div>
            <div
              className={`min-w-0 flex-1 rounded-lg px-3 py-1.5 ${live ? "bg-slate-800/60 ring-1 ring-sky-500/30" : ""}`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`text-sm font-semibold ${step.status === "skipped" || step.status === "pending" ? "text-slate-500" : "text-slate-100"}`}
                >
                  {step.title}
                </span>
                <PartnerBadge partner={partner} label={step.tech} />
                {step.started_at && (
                  <span className="ml-auto font-mono text-[11px] text-slate-500">
                    {clock(step.started_at)}
                    {step.finished_at ? ` · ${seconds(step.started_at, step.finished_at)}` : ""}
                  </span>
                )}
              </div>
              {step.detail && <p className="mt-0.5 text-xs text-slate-400">{step.detail}</p>}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function RootCausePanel({ p }: { p: Progress }) {
  const rc = p.root_cause;
  return (
    <Card
      title="AI root cause"
      icon={<Brain className="h-4 w-4 text-sky-300" />}
      badge={<PartnerBadge partner="jarvislabs" label="Jarvislabs" />}
    >
      {!rc ? (
        <Empty>
          {p.steps.find((s) => s.key === "analyze_root_cause")?.status === "running"
            ? "The model is reading the evidence…"
            : "Not analysed yet."}
        </Empty>
      ) : (
        <div className="space-y-3">
          <p className="text-base font-semibold text-slate-100">{rc.summary}</p>
          <p className="text-sm text-slate-300">{rc.root_cause}</p>
          <div>
            <div className="mb-1 flex justify-between text-xs text-slate-400">
              <span>Confidence</span>
              <span className="font-mono text-slate-200">{pct(rc.confidence, 0)}</span>
            </div>
            <div className="h-1.5 rounded-full bg-slate-800">
              <div
                className="h-1.5 rounded-full bg-gradient-to-r from-sky-500 to-violet-500"
                style={{ width: `${Math.round(rc.confidence * 100)}%` }}
              />
            </div>
          </div>
          <ul className="space-y-1">
            {rc.evidence.map((e) => (
              <li key={e} className="flex gap-2 text-xs text-slate-300">
                <span className="text-sky-400">▸</span>
                {e}
              </li>
            ))}
          </ul>
          <div className="rounded-xl border border-sky-500/30 bg-sky-500/5 p-3">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-sky-300">
              Proposed fix · {rc.runbook}
            </div>
            <p className="mt-1 text-sm text-slate-200">{rc.runbook_reason}</p>
          </div>
          <div className="flex flex-wrap gap-3 font-mono text-[11px] text-slate-500">
            <span>{rc.model}</span>
            <span>{ms(rc.latency_ms)}</span>
            {rc.total_tokens !== null && <span>{rc.total_tokens} tokens</span>}
            <span>identifiers masked before sending</span>
          </div>
        </div>
      )}
    </Card>
  );
}

function MemoryPanel({ p }: { p: Progress }) {
  const recall = p.recall;
  const saved = p.steps.find((s) => s.key === "save_memory");
  return (
    <Card
      title="Incident memory"
      icon={<Database className="h-4 w-4 text-amber-300" />}
      badge={<PartnerBadge partner="supermemory" label="Supermemory" />}
    >
      {!recall ? (
        <Empty>Searching past incidents…</Empty>
      ) : !recall.configured ? (
        <Empty>Supermemory API key not set: investigating without memory.</Empty>
      ) : recall.hits.length === 0 ? (
        <Empty>No similar past incidents.</Empty>
      ) : (
        <ul className="space-y-2">
          {recall.hits.map((hit) => (
            <li key={`${hit.title}-${hit.similarity}`} className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-amber-200">{hit.title}</span>
                <Pill tone="warn">{pct(hit.similarity, 0)} match</Pill>
              </div>
              <p className="mt-1 line-clamp-3 text-xs text-slate-300">{hit.text}</p>
            </li>
          ))}
        </ul>
      )}
      {saved?.status === "done" && (
        <p className="mt-3 flex items-center gap-2 text-xs text-emerald-300">
          <Sparkles className="h-3.5 w-3.5" /> {saved.detail}
        </p>
      )}
    </Card>
  );
}

function ApprovalPanel({
  p,
  workflowId,
  runId,
  onDecided,
}: {
  p: Progress;
  workflowId: string;
  runId: string;
  onDecided: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const waiting = p.status === "awaiting_approval";

  async function decide(approved: boolean) {
    setBusy(true);
    setError(null);
    try {
      await api.decide(workflowId, runId, approved);
      onDecided();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card
      title="Human approval"
      icon={<ShieldCheck className="h-4 w-4 text-violet-300" />}
      badge={<PartnerBadge partner="temporal" label="Temporal signal" />}
    >
      {waiting && p.root_cause ? (
        <div className="space-y-3">
          <p className="text-sm text-slate-300">
            The workflow is paused, durably, until a human decides. Approve to run{" "}
            <span className="font-mono text-sky-300">{p.root_cause.runbook}</span> on {p.bank}.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => decide(true)}
              className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-emerald-900/40 hover:bg-emerald-500 disabled:opacity-50"
            >
              <ThumbsUp className="h-4 w-4" /> Approve fix
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => decide(false)}
              className="flex items-center justify-center gap-2 rounded-xl border border-slate-700 px-4 py-3 text-sm font-semibold text-slate-200 hover:bg-slate-800 disabled:opacity-50"
            >
              <ThumbsDown className="h-4 w-4" /> Reject
            </button>
          </div>
        </div>
      ) : p.decision ? (
        <p className="text-sm text-slate-300">
          {p.decision.approved ? "Approved" : "Rejected"} by{" "}
          <span className="font-semibold text-slate-100">{p.decision.by}</span>
          {p.runbook && (
            <span className="mt-2 block text-xs text-slate-400">
              {p.runbook.action}: {p.runbook.detail}
            </span>
          )}
        </p>
      ) : (
        <Empty>
          {p.status === "escalated" ? "No automatic fix proposed: escalated." : "Waiting for the AI proposal…"}
        </Empty>
      )}
      <ErrorNote message={error} />
    </Card>
  );
}

function RecoveryPanel({ p }: { p: Progress }) {
  return (
    <Card
      title="Recovery check"
      icon={<HeartPulse className="h-4 w-4 text-emerald-300" />}
      badge={<PartnerBadge partner="temporal" label="Temporal timers" />}
    >
      {p.verification.length === 0 ? (
        <Empty>Runs after the fix is applied.</Empty>
      ) : (
        <div className="flex items-end gap-1.5">
          {p.verification.map((c) => (
            <div key={c.checked_at} className="flex flex-1 flex-col items-center gap-1">
              <div className="flex h-16 w-full items-end rounded bg-slate-800/60">
                <div
                  className={`w-full rounded ${c.healthy ? "bg-emerald-500" : "bg-rose-500/70"}`}
                  style={{ height: `${Math.max(4, Math.round((c.success_rate ?? 0) * 100))}%` }}
                />
              </div>
              <span className="font-mono text-[10px] text-slate-400">{pct(c.success_rate, 0)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function IncidentDetail({ workflowId, runId }: { workflowId: string; runId: string }) {
  const { data, error, refresh } = usePoll(() => api.incident(workflowId, runId), 1500);

  if (!data) {
    return (
      <Card title="Incident" icon={<Workflow className="h-4 w-4 text-violet-300" />}>
        {error ? <ErrorNote message={error} /> : <Empty>Loading incident…</Empty>}
      </Card>
    );
  }

  const p = data.progress;
  const status = INCIDENT_TONE[p.status];
  const t = p.trigger;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-800/80 bg-slate-900/60 px-5 py-4">
        <div className="flex items-center gap-4">
          <div className="rounded-xl bg-rose-500/10 p-2.5">
            <TriangleAlert className="h-6 w-6 text-rose-400" />
          </div>
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-bold text-slate-50">{p.bank} payment incident</h2>
              <Pill tone={status.tone}>{status.label}</Pill>
            </div>
            <p className="text-xs text-slate-400">
              Detected {clock(p.opened_at)}: {t.method} success {pct(t.success_rate)} over {t.total}{" "}
              payments, top error <span className="font-mono">{t.top_error_code ?? "n/a"}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          {p.resolution_seconds !== null && (
            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-center">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-emerald-300">
                Resolved in
              </div>
              <div className="font-mono text-2xl font-bold text-emerald-200">
                {Math.round(p.resolution_seconds)}s
              </div>
            </div>
          )}
          <a
            href={temporalUiUrl(workflowId, data.run_id)}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-2 rounded-lg border border-violet-500/40 bg-violet-500/10 px-3 py-2 text-xs font-semibold text-violet-200 hover:bg-violet-500/20"
          >
            <Gauge className="h-4 w-4" /> Open in Temporal UI <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-5">
        <Card
          title="Investigation timeline"
          icon={<Workflow className="h-4 w-4 text-violet-300" />}
          badge={<PartnerBadge partner="temporal" label="Temporal workflow" />}
          className="xl:col-span-2"
        >
          <Timeline steps={p.steps} />
          <ErrorNote message={error} />
        </Card>
        <div className="space-y-4 xl:col-span-3">
          <RootCausePanel p={p} />
          <div className="grid gap-4 lg:grid-cols-2">
            <MemoryPanel p={p} />
            <ApprovalPanel p={p} workflowId={workflowId} runId={data.run_id} onDecided={refresh} />
          </div>
          <RecoveryPanel p={p} />
        </div>
      </div>
    </div>
  );
}
