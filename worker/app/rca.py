"""Builds the LLM prompt and checks its answer. Pure: the HTTP call lives in activities.py."""

import json
import re
from typing import Any

from app.contracts import Evidence, Recall
from app.masking import mask_sensitive
from app.runbooks import RUNBOOKS

SYSTEM_PROMPT = """You are PayPulse, an SRE copilot for an Indian payment gateway.
You receive evidence about a payment incident and notes from similar past incidents.
Every number in the evidence was computed in SQL.

Rules:
- Use only the numbers given. Never calculate new numbers.
- Pick exactly one runbook from "allowed_runbooks".
- If the evidence does not clearly support an automatic fix, pick "escalate".

Reply with one JSON object and nothing else, with exactly these keys:
{
  "summary": "one sentence a non-engineer understands",
  "root_cause": "the most likely cause, one or two sentences",
  "confidence": 0.0 to 1.0,
  "evidence": ["three to five short facts from the data that support the cause"],
  "runbook": "one key from allowed_runbooks",
  "runbook_reason": "why this runbook; mention past incidents if they helped"
}"""


class RcaParseError(ValueError):
    """The model's answer was not the JSON we asked for. The activity retries."""


def build_messages(evidence: Evidence, recall: Recall) -> list[dict[str, str]]:
    payload = {
        "bank": evidence.bank,
        "evidence": evidence.breakdown,
        "recent_deploys": evidence.recent_deploys,
        "similar_past_incidents": [
            {"title": hit.title, "notes": hit.text, "similarity": hit.similarity}
            for hit in recall.hits
        ],
        "allowed_runbooks": RUNBOOKS,
    }
    user = mask_sensitive(json.dumps(payload, indent=1, default=str))
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def parse_root_cause(content: str) -> dict[str, Any]:
    # Take the outermost {...}: some models still wrap JSON in ``` fences.
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match is None:
        raise RcaParseError("no JSON object in model reply")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise RcaParseError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise RcaParseError("reply is not a JSON object")

    try:
        confidence = float(data.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise RcaParseError("confidence is not a number") from exc
    if not 0 <= confidence <= 1:
        raise RcaParseError(f"confidence {confidence} is outside 0..1")

    evidence = data.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise RcaParseError("evidence must be a non-empty list")

    runbook = data.get("runbook")
    if runbook not in RUNBOOKS:
        raise RcaParseError(f"runbook {runbook!r} is not in the allowed list")

    return {
        "summary": _text(data, "summary"),
        "root_cause": _text(data, "root_cause"),
        "confidence": confidence,
        "evidence": [str(item) for item in evidence[:6]],
        "runbook": runbook,
        "runbook_reason": _text(data, "runbook_reason"),
    }


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RcaParseError(f"{key} must be a non-empty string")
    return value.strip()
