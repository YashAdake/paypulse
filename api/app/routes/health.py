import asyncio
import contextlib
from datetime import timedelta

from fastapi import APIRouter, Request

from app import payment_service
from app.models import HealthResponse, Partner, StatusResponse
from app.payment_service import PaymentsDep
from app.temporal import TemporalDep

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    # Liveness only. Dependency status is /api/status, so a Temporal blip doesn't
    # make Docker restart the api.
    return HealthResponse()


@router.get("/status", response_model=StatusResponse)
async def status(request: Request, client: TemporalDep, http: PaymentsDep) -> StatusResponse:
    """Live status of each partner and system, for the Command Center's "Powered by" strip."""
    settings = request.app.state.settings
    timeout = settings.temporal_rpc_timeout_s

    async def temporal_ok() -> bool:
        with contextlib.suppress(Exception):
            return await client.service_client.check_health(timeout=timedelta(seconds=timeout))
        return False

    async def payments_ok() -> bool:
        with contextlib.suppress(Exception):
            await payment_service.call(http, "GET", "/healthz")
            return True
        return False

    temporal_up, payments_up = await asyncio.gather(temporal_ok(), payments_ok())

    def configured(key: str) -> str:
        return "configured" if key else "not_configured"

    partners = [
        Partner(
            key="temporal",
            name="Temporal",
            role="Durable incident workflow, approval signal, recovery timers",
            status="connected" if temporal_up else "down",
            detail=settings.temporal_address,
        ),
        Partner(
            key="jarvislabs",
            name="Jarvislabs",
            role="AI root cause on Token Factory (open model, OpenAI-compatible)",
            status=configured(settings.llm_api_key),
            detail=settings.llm_model,
        ),
        Partner(
            key="supermemory",
            name="Supermemory",
            role="Recalls past incidents and fixes; learns from each new one",
            status=configured(settings.supermemory_api_key),
            detail="incident memory",
        ),
        Partner(
            key="kepler",
            name="Kepler by RubixKube",
            role="Engineer-facing incident surface",
            status="planned",
            detail="integration in progress",
        ),
        Partner(
            key="payments",
            name="Payment service",
            role="System under watch: fake payments, chaos, stats in SQL",
            status="connected" if payments_up else "down",
            detail="Postgres 16",
        ),
    ]
    return StatusResponse(partners=partners)
