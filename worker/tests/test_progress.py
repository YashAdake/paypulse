from datetime import UTC, datetime, timedelta

import pytest

from app.contracts import Trigger
from app.progress import STEPS, IncidentStatus, Progress, StepStatus

T0 = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


def new_progress() -> Progress:
    trigger = Trigger("HDFC", "UPI", 0.39, 40, "BANK_TIMEOUT")
    return Progress(incident_id="run-1", bank="HDFC", trigger=trigger, opened_at=T0.isoformat())


def test_starts_with_all_eight_steps_pending() -> None:
    p = new_progress()
    assert [s.key for s in p.steps] == [spec.key for spec in STEPS]
    assert len(p.steps) == 8
    assert all(s.status is StepStatus.PENDING for s in p.steps)
    assert p.status is IncidentStatus.INVESTIGATING


def test_start_and_finish_record_times_and_detail() -> None:
    p = new_progress()
    p.start("gather_evidence", T0)
    assert p.step("gather_evidence").status is StepStatus.RUNNING
    p.finish("gather_evidence", T0 + timedelta(seconds=1), "ok")
    step = p.step("gather_evidence")
    assert step.status is StepStatus.DONE
    assert step.started_at == T0.isoformat()
    assert step.finished_at == (T0 + timedelta(seconds=1)).isoformat()
    assert step.detail == "ok"


def test_waiting_step_for_approval() -> None:
    p = new_progress()
    p.start("await_approval", T0, waiting=True)
    assert p.step("await_approval").status is StepStatus.WAITING


def test_close_skips_steps_that_never_ran() -> None:
    p = new_progress()
    p.start("gather_evidence", T0)
    p.fail("gather_evidence", T0, "payment-service down")
    p.close(IncidentStatus.FAILED, T0 + timedelta(seconds=5))
    assert p.status is IncidentStatus.FAILED
    assert p.closed_at == (T0 + timedelta(seconds=5)).isoformat()
    assert p.step("gather_evidence").status is StepStatus.FAILED
    rest = [s for s in p.steps if s.key != "gather_evidence"]
    assert all(s.status is StepStatus.SKIPPED for s in rest)
    assert all("failed" in (s.detail or "") for s in rest)


def test_resolution_time_measured_from_detection_to_recovery() -> None:
    p = new_progress()
    p.mark_recovered(T0 + timedelta(seconds=47, milliseconds=260))
    assert p.resolution_seconds == 47.3


def test_unknown_step_is_an_error() -> None:
    with pytest.raises(KeyError):
        new_progress().start("make_coffee", T0)
