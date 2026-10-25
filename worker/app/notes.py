"""One-line timeline notes for each step, and the postmortem saved to memory.

Pure formatting of results; no maths.
"""

from app.contracts import Evidence, HealthCheck, Recall, RootCause, RunbookResult
from app.progress import Progress


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate * 100:.1f}%"


def evidence(result: Evidence) -> str:
    errors = result.breakdown.get("errors") or []
    top = errors[0] if errors else None
    top_text = (
        f"top error {top['error_code']} ({_pct(top['share_of_failures'])} of failures)"
        if top
        else "no failures in window"
    )
    deploys = len(result.recent_deploys)
    return f"{result.bank}: {top_text}; {deploys} deploy(s) in the last hour"


def recall(result: Recall) -> str:
    if not result.configured:
        return "Supermemory not configured (SUPERMEMORY_API_KEY empty): no past incidents used"
    if not result.hits:
        return "No similar past incidents found"
    best = result.hits[0]
    return (
        f"{len(result.hits)} similar incident(s); "
        f"best match {best.title!r} ({_pct(best.similarity)})"
    )


def root_cause(result: RootCause) -> str:
    return (
        f"{result.root_cause} (confidence {_pct(result.confidence)}, "
        f"{result.model}, {result.latency_ms} ms)"
    )


def runbook(result: RunbookResult) -> str:
    return f"{result.action}: {result.detail}"


def recovered(check: HealthCheck, checks: int) -> str:
    return f"Success rate back to {_pct(check.success_rate)} after {checks} check(s)"


def postmortem(p: Progress) -> tuple[str, str]:
    """(title, markdown) for Supermemory, so the next investigation can recall this one."""
    rc = p.root_cause
    t = p.trigger
    day = p.opened_at[:10]
    title = f"{day} {p.bank} {t.top_error_code or 'payment failures'}"
    lines = [
        f"# {title}",
        "",
        f"Bank: {p.bank}. Trigger: {t.method} success rate {_pct(t.success_rate)} "
        f"over {t.total} payments, top error {t.top_error_code or 'n/a'}.",
    ]
    if rc is not None:
        lines += [
            f"Summary: {rc.summary}",
            f"Root cause: {rc.root_cause}",
            "Evidence:",
            *[f"- {item}" for item in rc.evidence],
        ]
    if p.runbook is not None:
        approver = p.decision.by if p.decision else "unknown"
        lines.append(
            f"Fix: {p.runbook.action} (runbook {p.runbook.runbook}), approved by {approver}."
        )
    if p.resolution_seconds is not None and p.verification:
        lines.append(
            f"Outcome: recovered {p.resolution_seconds:.0f}s after detection; "
            f"success rate back to {_pct(p.verification[-1].success_rate)}."
        )
    return title, "\n".join(lines)
