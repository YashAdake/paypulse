from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.db import PoolDep
from app.domain import Bank
from app.models import BreakdownResponse, StatsResponse, TimeseriesResponse
from app.services import stats

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    pool: PoolDep,
    window_seconds: Annotated[int, Query(ge=1, le=3600)] = 60,
) -> StatsResponse:
    async with pool.connection() as conn:
        groups = await stats.get_stats(conn, window_seconds)
    return StatsResponse.model_validate(
        {"window_seconds": window_seconds, "generated_at": datetime.now(UTC), "groups": groups}
    )


@router.get("/stats/timeseries", response_model=TimeseriesResponse)
async def get_timeseries(
    pool: PoolDep,
    window_seconds: Annotated[int, Query(ge=30, le=3600)] = 300,
    bucket_seconds: Annotated[int, Query(ge=5, le=300)] = 10,
) -> TimeseriesResponse:
    async with pool.connection() as conn:
        points = await stats.get_timeseries(conn, window_seconds, bucket_seconds)
    return TimeseriesResponse.model_validate(
        {"window_seconds": window_seconds, "bucket_seconds": bucket_seconds, "points": points}
    )


@router.get("/stats/breakdown", response_model=BreakdownResponse)
async def get_breakdown(
    pool: PoolDep,
    bank: Bank,
    window_seconds: Annotated[int, Query(ge=10, le=3600)] = 120,
    baseline_seconds: Annotated[int, Query(ge=60, le=86400)] = 1800,
) -> BreakdownResponse:
    """Evidence for one bank: per-method now vs before, error mix, and every bank for contrast."""
    async with pool.connection() as conn:
        breakdown = await stats.get_breakdown(conn, bank, window_seconds, baseline_seconds)
    return BreakdownResponse.model_validate(
        {
            "bank": bank,
            "window_seconds": window_seconds,
            "baseline_seconds": baseline_seconds,
            "generated_at": datetime.now(UTC),
            **breakdown,
        }
    )
