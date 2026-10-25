"""Request and response schemas for the Command Center API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Bank = Literal["HDFC", "SBI", "ICICI", "AXIS"]


class StrictModel(BaseModel):
    # Reject unknown fields so typos fail loudly instead of being ignored.
    model_config = ConfigDict(extra="forbid")


class LiveResponse(BaseModel):
    # Relayed from payment-service, which already validated these shapes.
    stats: dict[str, Any]
    timeseries: dict[str, Any]
    chaos: dict[str, Any]


class ChaosRequest(StrictModel):
    bank: Bank
    type: Literal["timeout", "decline"]
    rate: float = Field(ge=0, le=1)


class IncidentSummary(BaseModel):
    workflow_id: str
    run_id: str
    bank: str
    temporal_status: str
    started_at: datetime
    closed_at: datetime | None


class IncidentList(BaseModel):
    incidents: list[IncidentSummary]


class IncidentDetail(BaseModel):
    workflow_id: str
    run_id: str
    temporal_status: str
    # The workflow's own Progress object (worker/app/progress.py), straight from the query.
    progress: dict[str, Any]


class DecisionRequest(StrictModel):
    approved: bool
    run_id: str | None = Field(default=None, max_length=100)
    by: str = Field(default="Command Center", min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    workflow_id: str
    accepted: bool = True


class Partner(BaseModel):
    key: str
    name: str
    role: str
    status: Literal["connected", "configured", "not_configured", "down", "planned"]
    detail: str


class StatusResponse(BaseModel):
    partners: list[Partner]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
