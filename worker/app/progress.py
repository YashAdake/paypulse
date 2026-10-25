"""The incident's live state, read by the UI through a Temporal query.

Pure and deterministic: callers pass in the time (workflow.now()), never the wall clock.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.contracts import (
    ApprovalDecision,
    Evidence,
    HealthCheck,
    Recall,
    RootCause,
    RunbookResult,
    Trigger,
)


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


class IncidentStatus(StrEnum):
    INVESTIGATING = "investigating"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    FAILED = "failed"


@dataclass(frozen=True)
class StepSpec:
    key: str
    title: str
    # Which technology does the work, so the UI can credit it on the timeline.
    tech: str


STEPS: tuple[StepSpec, ...] = (
    StepSpec("gather_evidence", "Gather evidence", "Postgres SQL"),
    StepSpec("recall_memory", "Recall similar incidents", "Supermemory"),
    StepSpec("analyze_root_cause", "AI root cause", "Jarvislabs"),
    StepSpec("notify", "Notify on-call", "Command Center"),
    StepSpec("await_approval", "Human approval", "Temporal signal"),
    StepSpec("run_runbook", "Run runbook", "Temporal activity"),
    StepSpec("verify_recovery", "Verify recovery", "Temporal timers"),
    StepSpec("save_memory", "Save to memory", "Supermemory"),
)


@dataclass
class Step:
    key: str
    title: str
    tech: str
    status: StepStatus = StepStatus.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    detail: str | None = None


def _new_steps() -> list[Step]:
    return [Step(spec.key, spec.title, spec.tech) for spec in STEPS]


@dataclass
class Progress:
    incident_id: str
    bank: str
    trigger: Trigger
    opened_at: str
    status: IncidentStatus = IncidentStatus.INVESTIGATING
    closed_at: str | None = None
    resolution_seconds: float | None = None
    steps: list[Step] = field(default_factory=_new_steps)
    evidence: Evidence | None = None
    recall: Recall | None = None
    root_cause: RootCause | None = None
    decision: ApprovalDecision | None = None
    runbook: RunbookResult | None = None
    verification: list[HealthCheck] = field(default_factory=list)

    def step(self, key: str) -> Step:
        for step in self.steps:
            if step.key == key:
                return step
        raise KeyError(f"unknown step {key!r}")

    def start(self, key: str, now: datetime, *, waiting: bool = False) -> None:
        step = self.step(key)
        step.status = StepStatus.WAITING if waiting else StepStatus.RUNNING
        step.started_at = now.isoformat()

    def finish(self, key: str, now: datetime, detail: str) -> None:
        self._end(key, now, StepStatus.DONE, detail)

    def fail(self, key: str, now: datetime, detail: str) -> None:
        self._end(key, now, StepStatus.FAILED, detail)

    def skip(self, key: str, detail: str) -> None:
        step = self.step(key)
        step.status = StepStatus.SKIPPED
        step.detail = detail

    def mark_recovered(self, now: datetime) -> None:
        """Record time from detection to verified recovery: the headline demo number."""
        self.resolution_seconds = round(
            (now - datetime.fromisoformat(self.opened_at)).total_seconds(), 1
        )

    def close(self, status: IncidentStatus, now: datetime) -> None:
        """End the incident. Steps that never ran are marked skipped, so the UI shows why."""
        self.status = status
        self.closed_at = now.isoformat()
        for step in self.steps:
            if step.status is StepStatus.PENDING:
                step.status = StepStatus.SKIPPED
                step.detail = step.detail or f"Not run: incident {status.value}"

    def _end(self, key: str, now: datetime, status: StepStatus, detail: str) -> None:
        step = self.step(key)
        step.status = status
        step.finished_at = now.isoformat()
        step.detail = detail
