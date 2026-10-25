"""InvestigateIncident: the durable, step-by-step response to one bank's payment incident.

Workflow code must be deterministic: no I/O, no wall clock, no randomness. Every side
effect lives in an activity (activities.py); time comes from workflow.now().
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any, NoReturn

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from app import notes
    from app.activities import Activities
    from app.contracts import (
        DECISION_SIGNAL,
        PROGRESS_QUERY,
        WORKFLOW_TYPE,
        ApprovalDecision,
        HealthCheckRequest,
        IncidentInput,
        NotifyRequest,
        RcaRequest,
        Recall,
        RecallRequest,
        RunbookRequest,
        SaveMemoryRequest,
        WorkflowSettings,
    )
    from app.progress import IncidentStatus, Progress
    from app.runbooks import ESCALATE

_QUICK: dict[str, Any] = {
    "start_to_close_timeout": timedelta(seconds=30),
    "retry_policy": RetryPolicy(initial_interval=timedelta(seconds=1), maximum_attempts=3),
}
# The LLM can be slow, and a malformed answer is worth a couple of fresh attempts.
_LLM: dict[str, Any] = {
    "start_to_close_timeout": timedelta(seconds=90),
    "retry_policy": RetryPolicy(initial_interval=timedelta(seconds=2), maximum_attempts=3),
}


@workflow.defn(name=WORKFLOW_TYPE)
class InvestigateIncident:
    @workflow.init
    def __init__(self, inp: IncidentInput) -> None:
        # Built here, not in run(), so the UI can query progress from the first moment.
        self._progress = Progress(
            incident_id=workflow.info().run_id,
            bank=inp.bank,
            trigger=inp.trigger,
            opened_at=workflow.now().isoformat(),
        )
        self._decision: ApprovalDecision | None = None

    @workflow.query(name=PROGRESS_QUERY)
    def get_progress(self) -> Progress:
        return self._progress

    @workflow.signal(name=DECISION_SIGNAL)
    def submit_decision(self, decision: ApprovalDecision) -> None:
        # First decision wins: a double-click or a retried request can't flip it.
        if self._decision is None:
            self._decision = decision

    @workflow.run
    async def run(self, inp: IncidentInput) -> Progress:
        p = self._progress
        cfg = inp.settings

        p.evidence = await self._step(
            "gather_evidence", Activities.gather_evidence, inp, notes.evidence
        )
        # Memory is helpful, not essential: if Supermemory is down, investigate without it.
        p.recall = await self._step(
            "recall_memory",
            Activities.recall_memory,
            RecallRequest(inp.bank, inp.trigger),
            notes.recall,
            critical=False,
        ) or Recall(configured=True, query="", hits=[])
        p.root_cause = await self._step(
            "analyze_root_cause",
            Activities.analyze_root_cause,
            RcaRequest(p.evidence, p.recall),
            notes.root_cause,
            options=_LLM,
        )
        await self._step(
            "notify",
            Activities.notify,
            NotifyRequest(inp.bank, p.root_cause),
            lambda note: note.detail,
        )

        if p.root_cause.runbook == ESCALATE:
            p.skip("await_approval", "No automatic fix proposed: escalated to on-call")
            p.close(IncidentStatus.ESCALATED, workflow.now())
            return p

        if not await self._await_approval(cfg):
            return p

        p.status = IncidentStatus.REMEDIATING
        p.runbook = await self._step(
            "run_runbook",
            Activities.run_runbook,
            RunbookRequest(inp.bank, p.root_cause.runbook),
            notes.runbook,
        )

        if not await self._verify_recovery(inp.bank, cfg):
            p.close(IncidentStatus.UNRESOLVED, workflow.now())
            return p

        p.status = IncidentStatus.RESOLVED
        title, content = notes.postmortem(p)
        # Non-critical: the fix worked, so a failed memory write must not turn the incident red.
        await self._step(
            "save_memory",
            Activities.save_memory,
            SaveMemoryRequest(p.incident_id, inp.bank, title, content),
            lambda w: (
                "Saved for future incidents"
                if w.configured
                else "Supermemory not configured: postmortem not saved"
            ),
            critical=False,
        )
        p.close(IncidentStatus.RESOLVED, workflow.now())
        return p

    async def _await_approval(self, cfg: WorkflowSettings) -> bool:
        p = self._progress
        p.status = IncidentStatus.AWAITING_APPROVAL
        p.start("await_approval", workflow.now(), waiting=True)
        try:
            # A durable timer: the wait survives worker restarts.
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(seconds=cfg.approval_timeout_s),
            )
        except TimeoutError:
            p.fail(
                "await_approval",
                workflow.now(),
                f"No decision within {cfg.approval_timeout_s // 60} min",
            )
            p.close(IncidentStatus.EXPIRED, workflow.now())
            return False

        decision = self._decision
        assert decision is not None  # wait_condition returned, so it is set
        p.decision = decision
        note = f": {decision.note}" if decision.note else ""
        if not decision.approved:
            p.fail("await_approval", workflow.now(), f"Rejected by {decision.by}{note}")
            p.close(IncidentStatus.REJECTED, workflow.now())
            return False
        p.finish("await_approval", workflow.now(), f"Approved by {decision.by}{note}")
        return True

    async def _verify_recovery(self, bank: str, cfg: WorkflowSettings) -> bool:
        p = self._progress
        p.start("verify_recovery", workflow.now())
        request = HealthCheckRequest(
            bank, cfg.verify_window_s, cfg.verify_min_success_rate, cfg.verify_min_payments
        )
        for attempt in range(1, cfg.verify_max_checks + 1):
            if attempt > 1:
                await workflow.sleep(cfg.verify_interval_s)
            try:
                check = await workflow.execute_activity_method(
                    Activities.check_bank_health, request, **_QUICK
                )
            except ActivityError as err:
                self._fail_incident("verify_recovery", err)
            p.verification.append(check)
            if check.healthy:
                p.mark_recovered(workflow.now())
                p.finish("verify_recovery", workflow.now(), notes.recovered(check, attempt))
                return True
        p.fail(
            "verify_recovery",
            workflow.now(),
            f"Still unhealthy after {cfg.verify_max_checks} checks: escalate to on-call",
        )
        return False

    async def _step(
        self,
        key: str,
        activity: Callable[..., Any],
        arg: Any,
        note: Callable[[Any], str],
        *,
        options: dict[str, Any] = _QUICK,
        critical: bool = True,
    ) -> Any:
        """Run one activity and record it on the timeline.

        A non-critical step that fails is marked failed and returns None; a critical one
        fails the whole incident.
        """
        p = self._progress
        p.start(key, workflow.now())
        try:
            result = await workflow.execute_activity_method(activity, arg, **options)
        except ActivityError as err:
            if critical:
                self._fail_incident(key, err)
            p.fail(key, workflow.now(), _reason(err))
            return None
        p.finish(key, workflow.now(), note(result))
        return result

    def _fail_incident(self, key: str, err: ActivityError) -> NoReturn:
        reason = _reason(err)
        self._progress.fail(key, workflow.now(), reason)
        self._progress.close(IncidentStatus.FAILED, workflow.now())
        # ApplicationError fails the workflow run, so Temporal's UI shows it red too.
        raise ApplicationError(f"{key} failed: {reason}") from err


def _reason(err: ActivityError) -> str:
    return str(err.cause or err)
