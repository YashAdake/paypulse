"""Core vocabulary of the service.

Stdlib only on purpose: the simulator and its tests depend on this module and must
run anywhere, even without the web/DB packages installed.
"""

from dataclasses import dataclass
from enum import StrEnum


class Bank(StrEnum):
    HDFC = "HDFC"
    SBI = "SBI"
    ICICI = "ICICI"
    AXIS = "AXIS"


class Method(StrEnum):
    UPI = "UPI"
    CARD = "CARD"


class ChaosType(StrEnum):
    TIMEOUT = "timeout"
    DECLINE = "decline"


class PaymentStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class ErrorCode(StrEnum):
    # Bank-side failures: these are what an incident looks like.
    BANK_TIMEOUT = "BANK_TIMEOUT"
    ISSUER_DECLINED = "ISSUER_DECLINED"
    # Customer-side failures: normal background noise, not an incident.
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    INVALID_VPA = "INVALID_VPA"
    CARD_EXPIRED = "CARD_EXPIRED"


@dataclass(frozen=True)
class ChaosRule:
    bank: Bank
    type: ChaosType
    rate: float


class IdempotencyConflictError(Exception):
    """The same Idempotency-Key was sent with a different request body."""
