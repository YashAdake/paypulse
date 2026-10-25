import type { ReactNode } from "react";

export function Card({
  title,
  icon,
  badge,
  actions,
  children,
  className = "",
}: {
  title: string;
  icon?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-2xl border border-slate-800/80 bg-slate-900/60 shadow-xl shadow-black/20 backdrop-blur ${className}`}
    >
      <header className="flex items-center justify-between gap-3 border-b border-slate-800/80 px-5 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold tracking-wide text-slate-200">
          {icon}
          <span>{title}</span>
          {badge}
        </div>
        {actions}
      </header>
      <div className="p-5">{children}</div>
    </section>
  );
}

// One accent per partner, used everywhere that partner appears.
const PARTNER_STYLES: Record<string, string> = {
  temporal: "border-violet-400/40 bg-violet-500/10 text-violet-200",
  jarvislabs: "border-sky-400/40 bg-sky-500/10 text-sky-200",
  supermemory: "border-amber-400/40 bg-amber-500/10 text-amber-200",
  kepler: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200",
  postgres: "border-slate-500/40 bg-slate-500/10 text-slate-300",
};

export function partnerKeyForTech(tech: string): string {
  const t = tech.toLowerCase();
  if (t.includes("temporal")) return "temporal";
  if (t.includes("jarvis")) return "jarvislabs";
  if (t.includes("supermemory")) return "supermemory";
  if (t.includes("kepler") || t.includes("command center")) return "kepler";
  return "postgres";
}

export function PartnerBadge({ partner, label }: { partner: string; label: string }) {
  const style = PARTNER_STYLES[partner] ?? PARTNER_STYLES.postgres;
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${style}`}
    >
      {label}
    </span>
  );
}

const TONES = {
  good: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  bad: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  info: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  muted: "bg-slate-700/30 text-slate-400 border-slate-600/40",
} as const;

export type Tone = keyof typeof TONES;

export function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

export function Dot({ tone, pulse = false }: { tone: Tone; pulse?: boolean }) {
  const color = {
    good: "bg-emerald-400",
    warn: "bg-amber-400",
    bad: "bg-rose-500",
    info: "bg-sky-400",
    muted: "bg-slate-500",
  }[tone];
  return (
    <span className="relative inline-flex h-2.5 w-2.5">
      {pulse && (
        <span className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-60 ${color}`} />
      )}
      <span className={`relative inline-flex h-2.5 w-2.5 rounded-full ${color}`} />
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-slate-500">{children}</p>;
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
      {message}
    </p>
  );
}
