from datetime import UTC, datetime, timedelta

from app.detection import find_triggers, may_open_incident


def group(bank: str, method: str, rate: float, total: int = 40, error: str | None = None) -> dict:
    return {
        "bank": bank,
        "method": method,
        "success_rate": rate,
        "total": total,
        "top_error_code": error,
        "p95_latency_ms": 500,
    }


def test_healthy_banks_raise_nothing() -> None:
    groups = [group("HDFC", "UPI", 0.98), group("SBI", "CARD", 0.95)]
    assert find_triggers(groups, min_success_rate=0.9, min_payments=20) == []


def test_drop_below_threshold_triggers_with_details() -> None:
    [trigger] = find_triggers(
        [group("HDFC", "UPI", 0.39, error="BANK_TIMEOUT"), group("SBI", "UPI", 0.98)],
        min_success_rate=0.9,
        min_payments=20,
    )
    assert (trigger.bank, trigger.method, trigger.success_rate) == ("HDFC", "UPI", 0.39)
    assert trigger.top_error_code == "BANK_TIMEOUT"


def test_one_trigger_per_bank_using_its_worst_method() -> None:
    triggers = find_triggers(
        [group("HDFC", "UPI", 0.6), group("HDFC", "CARD", 0.3)],
        min_success_rate=0.9,
        min_payments=20,
    )
    assert [(t.bank, t.method) for t in triggers] == [("HDFC", "CARD")]


def test_low_volume_is_ignored() -> None:
    assert (
        find_triggers([group("AXIS", "UPI", 0.5, total=5)], min_success_rate=0.9, min_payments=20)
        == []
    )


def test_exactly_at_threshold_is_healthy() -> None:
    assert find_triggers([group("ICICI", "UPI", 0.9)], min_success_rate=0.9, min_payments=20) == []


def test_multiple_banks_sorted() -> None:
    triggers = find_triggers(
        [group("SBI", "UPI", 0.5), group("AXIS", "CARD", 0.4)],
        min_success_rate=0.9,
        min_payments=20,
    )
    assert [t.bank for t in triggers] == ["AXIS", "SBI"]


NOW = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def test_never_opened_bank_may_open() -> None:
    assert may_open_incident(False, None, NOW, cooldown_s=120)


def test_running_incident_blocks_a_second_one() -> None:
    assert not may_open_incident(True, None, NOW, cooldown_s=120)


def test_recently_closed_incident_is_in_cooldown() -> None:
    assert not may_open_incident(False, NOW - timedelta(seconds=30), NOW, cooldown_s=120)


def test_cooldown_expires() -> None:
    assert may_open_incident(False, NOW - timedelta(seconds=121), NOW, cooldown_s=120)
