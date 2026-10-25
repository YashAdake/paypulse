from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.db import PoolDep
from app.models import StatsResponse
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
