import asyncio
import logging
from datetime import UTC, datetime, timedelta

import httpx
from temporalio.client import Client, WorkflowExecutionStatus
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError, RPCStatusCode

from app.config import Settings
from app.contracts import WORKFLOW_TYPE, IncidentInput, Trigger, incident_workflow_id
from app.detection import find_triggers, may_open_incident

log = logging.getLogger(__name__)


class Detector:
    """Polls payment stats and starts an InvestigateIncident workflow when a bank drops."""

    def __init__(self, client: Client, payments: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._payments = payments
        self._settings = settings
        self._rpc_timeout = timedelta(seconds=settings.http_timeout_s)

    async def run(self) -> None:
        s = self._settings
        log.info(
            "detector started",
            extra={
                "interval_s": s.detector_interval_s,
                "window_s": s.detector_window_s,
                "min_success_rate": s.detector_min_success_rate,
                "min_payments": s.detector_min_payments,
            },
        )
        while True:
            try:
                await self.check_once()
            except Exception:
                # Keep watching through blips (a restart, a network hiccup); logged, not hidden.
                log.exception("detector check failed")
            await asyncio.sleep(s.detector_interval_s)

    async def check_once(self) -> None:
        s = self._settings
        resp = await self._payments.get("/stats", params={"window_seconds": s.detector_window_s})
        resp.raise_for_status()
        triggers = find_triggers(
            resp.json()["groups"], s.detector_min_success_rate, s.detector_min_payments
        )
        for trigger in triggers:
            await self._maybe_open_incident(trigger)

    async def _maybe_open_incident(self, trigger: Trigger) -> None:
        workflow_id = incident_workflow_id(trigger.bank)
        is_running, closed_at = await self._latest_run(workflow_id)
        if not may_open_incident(
            is_running, closed_at, datetime.now(UTC), self._settings.detector_cooldown_s
        ):
            return
        try:
            await self._client.start_workflow(
                WORKFLOW_TYPE,
                IncidentInput(
                    bank=trigger.bank,
                    trigger=trigger,
                    settings=self._settings.workflow_settings(),
                ),
                id=workflow_id,
                task_queue=self._settings.task_queue,
                rpc_timeout=self._rpc_timeout,
            )
        except WorkflowAlreadyStartedError:
            # Another check got there first; Temporal guarantees only one runs.
            return
        log.warning(
            "incident opened",
            extra={
                "workflow_id": workflow_id,
                "bank": trigger.bank,
                "method": trigger.method,
                "success_rate": trigger.success_rate,
                "top_error_code": trigger.top_error_code,
            },
        )

    async def _latest_run(self, workflow_id: str) -> tuple[bool, datetime | None]:
        """Ask Temporal, not local memory, about the bank's latest incident: restart-safe."""
        try:
            desc = await self._client.get_workflow_handle(workflow_id).describe(
                rpc_timeout=self._rpc_timeout
            )
        except RPCError as err:
            if err.status == RPCStatusCode.NOT_FOUND:
                return False, None
            raise
        return desc.status == WorkflowExecutionStatus.RUNNING, desc.close_time
