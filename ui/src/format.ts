export function pct(rate: number | null | undefined, digits = 1): string {
  return rate === null || rate === undefined ? "–" : `${(rate * 100).toFixed(digits)}%`;
}

export function ms(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`;
}

export function clock(iso: string | null | undefined): string {
  if (!iso) return "–";
  return new Date(iso).toLocaleTimeString([], { hour12: false });
}

export function seconds(from: string | null, to: string | null): string {
  if (!from) return "";
  const end = to ? new Date(to).getTime() : Date.now();
  const s = Math.max(0, (end - new Date(from).getTime()) / 1000);
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

/** Green / amber / red thresholds match the detector (alerts below 90%). */
export function health(rate: number | null | undefined): "good" | "warn" | "bad" | "none" {
  if (rate === null || rate === undefined) return "none";
  if (rate >= 0.95) return "good";
  if (rate >= 0.9) return "warn";
  return "bad";
}

export function temporalUiUrl(workflowId: string, runId: string): string {
  // Same host the Command Center is served from; Temporal's UI listens on 8233.
  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:8233/namespaces/default/workflows/${workflowId}/${runId}/history`;
}
