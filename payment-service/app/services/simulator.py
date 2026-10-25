"""Decides how a fake payment turns out. Pure: no I/O, randomness is passed in.

Latency is recorded, never slept, so the API and traffic generator stay fast while
the stats still look like a real incident.
"""

import math
import random
from dataclasses import dataclass

from app.domain import Bank, ChaosRule, ChaosType, ErrorCode, Method, PaymentStatus

BASELINE_SUCCESS_RATE = 0.98
# The gateway gives up on the bank after 10s, so timed-out payments all land near this.
TIMEOUT_LATENCY_MS = 10_000
_TIMEOUT_JITTER_MS = 250

# Banks differ a little so the dashboard doesn't look synthetic.
_MEDIAN_LATENCY_MS = {Bank.HDFC: 320, Bank.SBI: 450, Bank.ICICI: 300, Bank.AXIS: 380}
# Log-normal spread: p95 lands at about 1.8x the median, a realistic long tail.
_LATENCY_SIGMA = 0.35

_BASELINE_ERRORS = {
    Method.UPI: (ErrorCode.INSUFFICIENT_FUNDS, ErrorCode.INVALID_VPA),
    Method.CARD: (ErrorCode.INSUFFICIENT_FUNDS, ErrorCode.CARD_EXPIRED),
}


@dataclass(frozen=True)
class Outcome:
    status: PaymentStatus
    error_code: ErrorCode | None
    latency_ms: int


def simulate(bank: Bank, method: Method, chaos: ChaosRule | None, rng: random.Random) -> Outcome:
    """Chaos is rolled first, then the normal 98%, so success = (1 - rate) * 0.98."""
    if chaos is not None and chaos.bank != bank:
        raise ValueError(f"chaos rule for {chaos.bank} applied to a {bank} payment")

    if chaos is not None and rng.random() < chaos.rate:
        return _chaos_failure(bank, chaos.type, rng)

    latency_ms = _normal_latency_ms(bank, rng)
    if rng.random() < BASELINE_SUCCESS_RATE:
        return Outcome(PaymentStatus.SUCCESS, None, latency_ms)
    return Outcome(PaymentStatus.FAILED, rng.choice(_BASELINE_ERRORS[method]), latency_ms)


def _chaos_failure(bank: Bank, chaos_type: ChaosType, rng: random.Random) -> Outcome:
    if chaos_type is ChaosType.TIMEOUT:
        latency_ms = TIMEOUT_LATENCY_MS + rng.randint(0, _TIMEOUT_JITTER_MS)
        return Outcome(PaymentStatus.FAILED, ErrorCode.BANK_TIMEOUT, latency_ms)
    # A decline is a fast "no" from the bank, so latency stays normal.
    return Outcome(PaymentStatus.FAILED, ErrorCode.ISSUER_DECLINED, _normal_latency_ms(bank, rng))


def _normal_latency_ms(bank: Bank, rng: random.Random) -> int:
    median = _MEDIAN_LATENCY_MS[bank]
    return max(1, round(rng.lognormvariate(math.log(median), _LATENCY_SIGMA)))
