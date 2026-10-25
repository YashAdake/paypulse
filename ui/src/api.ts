// Types mirror the api service (api/app/models.py) and the workflow's Progress
// (worker/app/progress.py). The browser only ever talks to /api on the same origin.

export const BANKS = ["HDFC", "SBI", "ICICI", "AXIS"] as const;
export type Bank = (typeof BANKS)[number];
export const METHODS = ["UPI", "CARD"] as const;

export interface StatsGroup {
  bank: string;
  method: string;
  total: number;
  success_rate: number;
  top_error_code: string | null;
  p95_latency_ms: number;
}

export interface TimeseriesPoint {
  bank: string;
  bucket_start: string;
  total: number;
  success_rate: number;
}

export interface ChaosRule {
  bank: string;
  type: string;
  rate: number;
  updated_at: string;
}

export interface LiveData {
  stats: { window_seconds: number; generated_at: string; groups: StatsGroup[] };
  timeseries: { window_seconds: number; bucket_seconds: number; points: TimeseriesPoint[] };
  chaos: { rules: ChaosRule[] };
}

export interface Partner {
  key: string;
  name: string;
  role: string;
  status: "connected" | "configured" | "not_configured" | "down" | "planned";
  detail: string;
}

export interface IncidentSummary {
  workflow_id: string;
  run_id: string;
  bank: string;
  temporal_status: string;
  started_at: string;
  closed_at: string | null;
}

export type StepStatus = "pending" | "running" | "waiting" | "done" | "failed" | "skipped";
export type IncidentStatus =
  | "investigating"
  | "awaiting_approval"
  | "remediating"
  | "resolved"
  | "unresolved"
  | "rejected"
  | "expired"
  | "escalated"
  | "failed";

export interface Step {
  key: string;
  title: string;
  tech: string;
  status: StepStatus;
  started_at: string | null;
  finished_at: string | null;
  detail: string | null;
}

export interface Trigger {
  bank: string;
  method: string;
  success_rate: number;
  total: number;
  top_error_code: string | null;
}

export interface MethodBreakdown {
  method: string;
  current_total: number;
  current_success_rate: number | null;
  current_p95_latency_ms: number | null;
  baseline_total: number;
  baseline_success_rate: number | null;
  baseline_p95_latency_ms: number | null;
}

export interface ErrorShare {
  error_code: string;
  count: number;
  share_of_failures: number;
  avg_latency_ms: number;
}

export interface Deploy {
  id: number;
  service: string;
  version: string;
  description: string | null;
  created_at: string;
}

export interface Evidence {
  bank: string;
  breakdown: {
    by_method: MethodBreakdown[];
    errors: ErrorShare[];
    all_banks: { bank: string; total: number; success_rate: number }[];
  };
  recent_deploys: Deploy[];
}

export interface MemoryHit {
  title: string;
  text: string;
  similarity: number;
}

export interface Recall {
  configured: boolean;
  query: string;
  hits: MemoryHit[];
}

export interface RootCause {
  summary: string;
  root_cause: string;
  confidence: number;
  evidence: string[];
  runbook: string;
  runbook_reason: string;
  model: string;
  latency_ms: number;
  total_tokens: number | null;
}

export interface Decision {
  approved: boolean;
  by: string;
  note: string | null;
}

export interface RunbookResult {
  runbook: string;
  action: string;
  detail: string;
}

export interface HealthCheck {
  checked_at: string;
  total: number;
  success_rate: number | null;
  healthy: boolean;
}

export interface Progress {
  incident_id: string;
  bank: string;
  trigger: Trigger;
  opened_at: string;
  status: IncidentStatus;
  closed_at: string | null;
  resolution_seconds: number | null;
  steps: Step[];
  evidence: Evidence | null;
  recall: Recall | null;
  root_cause: RootCause | null;
  decision: Decision | null;
  runbook: RunbookResult | null;
  verification: HealthCheck[];
}

export interface IncidentDetail {
  workflow_id: string;
  run_id: string;
  temporal_status: string;
  progress: Progress;
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: init.body ? { "Content-Type": "application/json" } : undefined,
  });
  // Every api error has the shape {"error": {"message": ...}}; fall back to the status text.
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    throw new ApiError(resp.status, body?.error?.message ?? resp.statusText);
  }
  return body as T;
}

export const api = {
  live: () => request<LiveData>("/api/live"),
  status: () => request<{ partners: Partner[] }>("/api/status"),
  incidents: () => request<{ incidents: IncidentSummary[] }>("/api/incidents"),
  incident: (workflowId: string, runId: string) =>
    request<IncidentDetail>(
      `/api/incidents/${workflowId}?run_id=${encodeURIComponent(runId)}`,
    ),
  decide: (workflowId: string, runId: string, approved: boolean) =>
    request<{ accepted: boolean }>(`/api/incidents/${workflowId}/decision`, {
      method: "POST",
      body: JSON.stringify({ approved, run_id: runId, by: "Command Center" }),
    }),
  injectChaos: (bank: Bank, type: "timeout" | "decline", rate: number) =>
    request<ChaosRule>("/api/chaos", {
      method: "POST",
      body: JSON.stringify({ bank, type, rate }),
    }),
  clearChaos: () => request<{ removed: string[] }>("/api/chaos", { method: "DELETE" }),
};
