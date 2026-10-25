import random

import pytest

from app.domain import Bank, ChaosRule, ChaosType, ErrorCode, Method, PaymentStatus
from app.services.simulator import BASELINE_SUCCESS_RATE, TIMEOUT_LATENCY_MS, Outcome, simulate

# Large enough that sampling noise stays well inside the tolerances below.
N = 20_000


def run(bank: Bank, method: Method, chaos: ChaosRule | None, seed: int = 7) -> list[Outcome]:
    rng = random.Random(seed)
    return [simulate(bank, method, chaos, rng) for _ in range(N)]


def success_rate(outcomes: list[Outcome]) -> float:
    return sum(o.status is PaymentStatus.SUCCESS for o in outcomes) / len(outcomes)


@pytest.mark.parametrize("bank", list(Bank))
def test_without_chaos_about_98_percent_succeed(bank: Bank) -> None:
    assert success_rate(run(bank, Method.UPI, None)) == pytest.approx(0.98, abs=0.01)


@pytest.mark.parametrize(
    ("method", "allowed"),
    [
        (Method.UPI, {ErrorCode.INSUFFICIENT_FUNDS, ErrorCode.INVALID_VPA}),
        (Method.CARD, {ErrorCode.INSUFFICIENT_FUNDS, ErrorCode.CARD_EXPIRED}),
    ],
)
def test_normal_failures_use_customer_side_codes_for_the_method(
    method: Method, allowed: set[ErrorCode]
) -> None:
    codes = {o.error_code for o in run(Bank.SBI, method, None) if o.status is PaymentStatus.FAILED}
    assert codes == allowed


def test_successes_have_no_error_code_and_normal_latency() -> None:
    successes = [o for o in run(Bank.HDFC, Method.CARD, None) if o.status is PaymentStatus.SUCCESS]
    assert all(o.error_code is None for o in successes)
    assert all(0 < o.latency_ms < TIMEOUT_LATENCY_MS for o in successes)


@pytest.mark.parametrize("rate", [0.0, 0.3, 0.6, 1.0])
def test_chaos_rate_scales_success_rate(rate: float) -> None:
    chaos = ChaosRule(Bank.HDFC, ChaosType.TIMEOUT, rate)
    expected = (1 - rate) * BASELINE_SUCCESS_RATE
    assert success_rate(run(Bank.HDFC, Method.UPI, chaos)) == pytest.approx(expected, abs=0.015)


def test_timeout_chaos_fails_with_bank_timeout_at_the_gateway_limit() -> None:
    outcomes = run(Bank.HDFC, Method.UPI, ChaosRule(Bank.HDFC, ChaosType.TIMEOUT, 1.0))
    assert all(o.status is PaymentStatus.FAILED for o in outcomes)
    assert all(o.error_code is ErrorCode.BANK_TIMEOUT for o in outcomes)
    assert all(o.latency_ms >= TIMEOUT_LATENCY_MS for o in outcomes)


def test_decline_chaos_fails_fast_with_issuer_declined() -> None:
    outcomes = run(Bank.HDFC, Method.CARD, ChaosRule(Bank.HDFC, ChaosType.DECLINE, 1.0))
    assert all(o.error_code is ErrorCode.ISSUER_DECLINED for o in outcomes)
    assert all(o.latency_ms < TIMEOUT_LATENCY_MS for o in outcomes)


def test_rule_for_another_bank_is_rejected() -> None:
    hdfc_rule = ChaosRule(Bank.HDFC, ChaosType.TIMEOUT, 1.0)
    with pytest.raises(ValueError, match="HDFC"):
        simulate(Bank.SBI, Method.UPI, hdfc_rule, random.Random(1))
