from fastapi import APIRouter

from app.db import PoolDep
from app.models import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(pool: PoolDep) -> HealthResponse:
    # Touch the DB so "healthy" means "can actually serve payments"; a DB failure
    # surfaces as 503 through the shared error handler.
    async with pool.connection() as conn:
        await conn.execute("SELECT 1")
    return HealthResponse()
