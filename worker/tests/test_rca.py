import json

import pytest

from app.contracts import Evidence, MemoryHit, Recall
from app.rca import RcaParseError, build_messages, parse_root_cause

GOOD = {
    "summary": "HDFC payments are timing out.",
    "root_cause": "HDFC connector is stuck waiting on the bank gateway.",
    "confidence": 0.92,
    "evidence": ["HDFC UPI success 39% vs 98% baseline", "BANK_TIMEOUT is 100% of failures"],
    "runbook": "restart_bank_connector",
    "runbook_reason": "Same pattern as the 12 Aug incident, fixed by a connector restart.",
}


def test_parses_a_valid_answer() -> None:
    parsed = parse_root_cause(json.dumps(GOOD))
    assert parsed["runbook"] == "restart_bank_connector"
    assert parsed["confidence"] == 0.92
    assert parsed["evidence"] == GOOD["evidence"]


def test_accepts_json_wrapped_in_code_fences() -> None:
    assert parse_root_cause(f"```json\n{json.dumps(GOOD)}\n```")["summary"] == GOOD["summary"]


@pytest.mark.parametrize(
    "change",
    [
        {"runbook": "rm -rf /"},  # anything outside the allow-list is refused
        {"confidence": 1.5},
        {"confidence": "high"},
        {"evidence": []},
        {"summary": ""},
        {"root_cause": None},
    ],
)
def test_rejects_answers_that_break_the_contract(change: dict) -> None:
    with pytest.raises(RcaParseError):
        parse_root_cause(json.dumps({**GOOD, **change}))


def test_rejects_non_json() -> None:
    with pytest.raises(RcaParseError):
        parse_root_cause("I think it is the bank.")


def test_prompt_contains_evidence_memories_and_masks_identifiers() -> None:
    evidence = Evidence(
        bank="HDFC",
        breakdown={"errors": [{"error_code": "BANK_TIMEOUT", "count": 30}]},
        recent_deploys=[{"service": "hdfc-connector", "description": "card 4111111111111111"}],
    )
    recall = Recall(
        configured=True,
        query="q",
        hits=[MemoryHit("2026-08-12 HDFC timeouts", "Fixed by connector restart", 0.81)],
    )
    system, user = build_messages(evidence, recall)
    assert system["role"] == "system" and "JSON" in system["content"]
    assert "BANK_TIMEOUT" in user["content"]
    assert "2026-08-12 HDFC timeouts" in user["content"]
    assert "restart_bank_connector" in user["content"]
    assert "4111111111111111" not in user["content"]
