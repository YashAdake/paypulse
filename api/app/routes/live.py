import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Query

from app import payment_service
from app.models import Bank, ChaosRequest, LiveResponse
from app.payment_service import PaymentsDep

router = APIRouter(prefix="/api", tags=["live"])


@router.get("/live", response_model=LiveResponse)
async def live(
    http: PaymentsDep,
    window_seconds: Annotated[int, Query(ge=10, le=3600)] = 60,
    history_seconds: Annotated[int, Query(ge=60, le=3600)] = 300,
) -> LiveResponse:
    """Everything the live panel needs in one call, fetched in parallel."""
    stats, timeseries, chaos = await asyncio.gather(
        payment_service.call(http, "GET", "/stats", params={"window_seconds": window_seconds}),
        payment_service.call(
            http,
            "GET",
            "/stats/timeseries",
            params={"window_seconds": history_seconds, "bucket_seconds": 10},
        ),
        payment_service.call(http, "GET", "/chaos"),
    )
    return LiveResponse(stats=stats, timeseries=timeseries, chaos=chaos)


# Demo controls: the presenter breaks and heals banks from the Command Center.
@router.post("/chaos")
async def set_chaos(body: ChaosRequest, http: PaymentsDep) -> Any:
    return await payment_service.call(http, "POST", "/chaos", json=body.model_dump())


@router.delete("/chaos")
async def clear_chaos(http: PaymentsDep) -> Any:
    return await payment_service.call(http, "DELETE", "/chaos")


@router.delete("/chaos/{bank}")
async def clear_bank_chaos(bank: Bank, http: PaymentsDep) -> Any:
    return await payment_service.call(http, "DELETE", f"/chaos/{bank}")
