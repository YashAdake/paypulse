"""Data passed between the detector, the workflow and its activities.

Plain dataclasses (stdlib only): Temporal serialises them to JSON, and the workflow
sandbox can import them safely.
"""

from dataclasses import dataclass, field
from typing import Any

# Names the api service uses to talk to the workflow. Keep in sync with api/app/routes/incidents.py.
WORKFLOW_TYPE = "InvestigateIncident"
PROGRESS_QUERY = "get_progress"
DECISION_SIGNAL = "submit_decision"


def incident_workflow_id(bank: str) -> str:
    # One fixed ID per bank: Temporal refuses a second running workflow with the same ID,
    # so a bank can never have two open incidents.
    return f"incident-{bank}"


@dataclass
class Trigger:
    """What the detector saw: the worst bank+method group below the threshold."""

    bank: str
    method: str
    success_rate: float
    total: int
    top_error_code: str | None


@dataclass
class WorkflowSettings:
    """Config the workflow needs. Passed in, because workflow code must not read env vars."""

    approval_timeout_s: int = 900
    evidence_window_s: int = 120
    evidence_baseline_s: int = 1800
    verify_window_s: int = 20
    verify_interval_s: int = 10
    verify_max_checks: int = 12
    verify_min_success_rate: float = 0.93
    verify_min_payments: int = 10


@dataclass
class IncidentInput:
    bank: str
    trigger: Trigger
    settings: WorkflowSettings = field(default_factory=WorkflowSettings)


@dataclass
class ApprovalDecision:
    approved: bool
    by: str = "engineer"
    note: str | None = None


@dataclass
class Evidence:
    bank: str
    # From payment-service /stats/breakdown: every number here was computed in SQL.
    breakdown: dict[str, Any]
    recent_deploys: list[dict[str, Any]]


@dataclass
class MemoryHit:
    title: str
    text: str
    similarity: float


@dataclass
class RecallRequest:
    bank: str
    trigger: Trigger


@dataclass
class Recall:
    configured: bool
    query: str
    hits: list[MemoryHit] = field(default_factory=list)


@dataclass
class RcaRequest:
    evidence: Evidence
    recall: Recall


@dataclass
class RootCause:
    summary: str
    root_cause: str
    confidence: float
    evidence: list[str]
    runbook: str
    runbook_reason: str
    model: str
    latency_ms: int
    total_tokens: int | None


@dataclass
class NotifyRequest:
    bank: str
    root_cause: RootCause


@dataclass
class RunbookRequest:
    bank: str
    runbook: str


@dataclass
class RunbookResult:
    runbook: str
    action: str
    detail: str


@dataclass
class HealthCheckRequest:
    bank: str
    window_s: int
    min_success_rate: float
    min_payments: int


@dataclass
class HealthCheck:
    checked_at: str
    total: int
    success_rate: float | None
    healthy: bool


@dataclass
class SaveMemoryRequest:
    incident_id: str
    bank: str
    title: str
    content: str


@dataclass
class MemoryWrite:
    configured: bool
    document_id: str | None = None


@dataclass
class StepNote:
    """What an activity reports for the timeline."""

    detail: str
