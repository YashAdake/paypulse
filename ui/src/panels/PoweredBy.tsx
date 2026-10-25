import { Brain, Database, Radio, Server, Workflow } from "lucide-react";
import type { ReactNode } from "react";
import type { Partner } from "../api";
import { Dot, type Tone } from "../components";

const ICONS: Record<string, ReactNode> = {
  temporal: <Workflow className="h-5 w-5 text-violet-300" />,
  jarvislabs: <Brain className="h-5 w-5 text-sky-300" />,
  supermemory: <Database className="h-5 w-5 text-amber-300" />,
  kepler: <Radio className="h-5 w-5 text-emerald-300" />,
  payments: <Server className="h-5 w-5 text-slate-300" />,
};

const STATUS: Record<Partner["status"], { tone: Tone; label: string }> = {
  connected: { tone: "good", label: "Live" },
  configured: { tone: "good", label: "Ready" },
  not_configured: { tone: "warn", label: "No API key" },
  down: { tone: "bad", label: "Down" },
  planned: { tone: "muted", label: "Coming soon" },
};

export function PoweredBy({ partners }: { partners: Partner[] | undefined }) {
  if (!partners) {
    return <div className="h-[76px] animate-pulse rounded-2xl bg-slate-900/60" />;
  }
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      {partners.map((p) => {
        const s = STATUS[p.status];
        return (
          <div
            key={p.key}
            title={p.role}
            className="flex items-center gap-3 rounded-2xl border border-slate-800/80 bg-slate-900/60 px-4 py-3"
          >
            <div className="rounded-xl bg-slate-800/80 p-2">{ICONS[p.key]}</div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-semibold text-slate-100">{p.name}</span>
                <span className="flex items-center gap-1.5 text-[11px] text-slate-400">
                  <Dot tone={s.tone} pulse={p.status === "connected"} />
                  {s.label}
                </span>
              </div>
              <p className="truncate text-xs text-slate-400">{p.role}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
