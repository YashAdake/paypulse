"""Every side effect of an investigation: HTTP calls to payment-service, the LLM and Supermemory.

Temporal retries failed activities, so each one must be safe to run twice.
"""

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from app import runbooks
from app.config import Settings
from app.contracts import (
    Evidence,
    HealthCheck,
    HealthCheckRequest,
    IncidentInput,
    MemoryHit,
    MemoryWrite,
    NotifyRequest,
    RcaRequest,
    Recall,
    RecallRequest,
    RootCause,
    RunbookRequest,
    RunbookResult,
    SaveMemoryRequest,
    StepNote,
)
from app.rca import build_messages, parse_root_cause

log = logging.getLogger(__name__)

# A bad request or a bad key won't fix itself: don't burn retries (or LLM credits) on it.
_NON_RETRYABLE_STATUS = {400, 401, 403, 404, 422}


def _check(resp: httpx.Response, what: str) -> None:
    if resp.is_success:
        return
    raise ApplicationError(
        f"{what} returned HTTP {resp.status_code}: {resp.text[:300]}",
        non_retryable=resp.status_code in _NON_RETRYABLE_STATUS,
    )


class Activities:
    def __init__(
        self,
        settings: Settings,
        payments: httpx.AsyncClient,
        llm: httpx.AsyncClient,
        memory: httpx.AsyncClient,
    ) -> None:
        self._settings = settings
        self._payments = payments
        self._llm = llm
        self._memory = memory

    @activity.defn(name="gather_evidence")
    async def gather_evidence(self, inp: IncidentInput) -> Evidence:
        cfg = inp.settings
        breakdown = await self._payments_get(
            "/stats/breakdown",
            {
                "bank": inp.bank,
                "window_seconds": cfg.evidence_window_s,
                "baseline_seconds": cfg.evidence_baseline_s,
            },
        )
        deploys = await self._payments_get("/deploys", {"since_seconds": 3600, "limit": 10})
        return Evidence(bank=inp.bank, breakdown=breakdown, recent_deploys=deploys["deploys"])

    @activity.defn(name="recall_memory")
    async def recall_memory(self, req: RecallRequest) -> Recall:
        error = req.trigger.top_error_code or "errors"
        query = (
            f"{req.bank} {req.trigger.method} payments failing with {error}, success rate dropped"
        )
        if not self._settings.supermemory_api_key:
            return Recall(configured=False, query=query)

        resp = await self._memory.post(
            "/v4/search",
            json={
                "q": query,
                "containerTag": self._settings.supermemory_container_tag,
                "limit": 3,
                "threshold": self._settings.supermemory_threshold,
                "searchMode": "hybrid",
                "include": {"documents": True},
            },
        )
        _check(resp, "Supermemory search")
        hits = []
        for result in resp.json().get("results", []):
            text = result.get("memory") or result.get("chunk") or ""
            if text:
                hits.append(
                    MemoryHit(
                        title=_memory_title(result),
                        text=text[:800],
                        similarity=round(float(result.get("similarity") or 0), 3),
                    )
                )
        return Recall(configured=True, query=query, hits=hits)

    @activity.defn(name="analyze_root_cause")
    async def analyze_root_cause(self, req: RcaRequest) -> RootCause:
        s = self._settings
        if not s.llm_api_key:
            raise ApplicationError("LLM_API_KEY is not set", non_retryable=True)

        started = time.perf_counter()
        resp = await self._llm.post(
            "/chat/completions",
            json={
                "model": s.llm_model,
                "messages": build_messages(req.evidence, req.recall),
                "temperature": 0.2,
                "max_tokens": s.llm_max_tokens,
                "response_format": {"type": "json_object"},
            },
        )
        _check(resp, "LLM")
        body = resp.json()
        content = body["choices"][0]["message"].get("content") or ""
        # A malformed answer raises here; Temporal retries the activity for a fresh answer.
        parsed = parse_root_cause(content)
        return RootCause(
            **parsed,
            model=body.get("model") or s.llm_model,
            latency_ms=round((time.perf_counter() - started) * 1000),
            total_tokens=(body.get("usage") or {}).get("total_tokens"),
        )

    @activity.defn(name="notify")
    async def notify(self, req: NotifyRequest) -> StepNote:
        # The Command Center shows the proposal as soon as this step completes.
        log.warning(
            "incident awaiting approval",
            extra={"bank": req.bank, "runbook": req.root_cause.runbook},
        )
        return StepNote(
            detail=f"Proposal posted to the Command Center for {req.bank}; "
            "Kepler (RubixKube) hand-off pending integration"
        )

    @activity.defn(name="run_runbook")
    async def run_runbook(self, req: RunbookRequest) -> RunbookResult:
        if req.runbook != "restart_bank_connector":
            raise ApplicationError(f"no automation for runbook {req.runbook!r}", non_retryable=True)
        # In the simulator the connector fault is the bank's chaos rule, so the restart
        # clears it. DELETE is idempotent: a retry after success just removes nothing.
        resp = await self._payments.delete(f"/chaos/{req.bank}")
        _check(resp, "payment-service chaos reset")
        removed = resp.json().get("removed") or []
        detail = (
            "connector restarted, stuck connections cleared"
            if removed
            else "connector restarted (no fault was active)"
        )
        return RunbookResult(
            runbook=req.runbook, action=runbooks.describe(req.runbook, req.bank), detail=detail
        )

    @activity.defn(name="check_bank_health")
    async def check_bank_health(self, req: HealthCheckRequest) -> HealthCheck:
        data = await self._payments_get(
            "/stats/breakdown",
            {"bank": req.bank, "window_seconds": req.window_s, "baseline_seconds": 60},
        )
        row = next((b for b in data["all_banks"] if b["bank"] == req.bank), None)
        total = row["total"] if row else 0
        rate = row["success_rate"] if row else None
        healthy = rate is not None and total >= req.min_payments and rate >= req.min_success_rate
        return HealthCheck(
            checked_at=datetime.now(UTC).isoformat(),
            total=total,
            success_rate=rate,
            healthy=healthy,
        )

    @activity.defn(name="save_memory")
    async def save_memory(self, req: SaveMemoryRequest) -> MemoryWrite:
        s = self._settings
        if not s.supermemory_api_key:
            return MemoryWrite(configured=False)
        # customId makes this idempotent: a retried activity updates the same document.
        resp = await self._memory.post(
            "/v3/documents",
            json={
                "content": req.content,
                "containerTag": s.supermemory_container_tag,
                "customId": f"paypulse-{req.incident_id}",
                "metadata": {"title": req.title, "bank": req.bank, "source": "paypulse"},
            },
        )
        _check(resp, "Supermemory add")
        return MemoryWrite(configured=True, document_id=resp.json().get("id"))

    async def _payments_get(self, path: str, params: dict[str, Any]) -> Any:
        resp = await self._payments.get(path, params=params)
        _check(resp, f"payment-service {path}")
        return resp.json()


def _memory_title(result: dict[str, Any]) -> str:
    metadata = result.get("metadata") or {}
    if metadata.get("title"):
        return str(metadata["title"])
    for doc in result.get("documents") or []:
        title = (doc.get("metadata") or {}).get("title") or doc.get("title")
        if title:
            return str(title)
    return "Past incident"
