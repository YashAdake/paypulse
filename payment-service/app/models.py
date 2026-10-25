"""Request and response schemas for the HTTP API."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import Header
from pydantic import BaseModel, ConfigDict, Field

from app.domain import Bank, ChaosType, ErrorCode, Method, PaymentStatus

# Optional on purpose: callers that retry (the Phase 5 runbook) send one; ad-hoc
# PowerShell calls don't have to.
IdempotencyKeyHeader = Annotated[
    str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
]


class StrictModel(BaseModel):
    # Reject unknown fields so typos like "rat" fail loudly instead of being ignored.
    model_config = ConfigDict(extra="forbid")


class PaymentRequest(StrictModel):
    bank: Bank
    method: Method
    # Integer paise: never use floats for money. Upper bound is ₹10 lakh.
    amount_paise: int = Field(gt=0, le=100_000_000)


class PaymentResponse(BaseModel):
    id: int
    bank: Bank
    method: Method
    amount_paise: int
    status: PaymentStatus
    error_code: ErrorCode | None
    latency_ms: int
    created_at: datetime


class ChaosRuleRequest(StrictModel):
    bank: Bank
    type: ChaosType
    rate: float = Field(ge=0, le=1, description="Share of this bank's payments to break")


class ChaosRuleResponse(BaseModel):
    bank: Bank
    type: ChaosType
    rate: float
    updated_at: datetime


class ChaosRuleList(BaseModel):
    rules: list[ChaosRuleResponse]


class ChaosDeleteResponse(BaseModel):
    # Empty when nothing was there: deleting is safe to repeat.
    removed: list[Bank]


class StatsGroup(BaseModel):
    bank: Bank
    method: Method
    total: int
    success_rate: float = Field(description="0..1")
    top_error_code: ErrorCode | None
    p95_latency_ms: int


class StatsResponse(BaseModel):
    window_seconds: int
    generated_at: datetime
    groups: list[StatsGroup]


class DeployRequest(StrictModel):
    service: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class DeployResponse(BaseModel):
    id: int
    service: str
    version: str
    description: str | None
    created_at: datetime


class DeployList(BaseModel):
    deploys: list[DeployResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
