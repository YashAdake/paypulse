from typing import Annotated, Any

from fastapi import APIRouter, Query, Response, status

from app.db import PoolDep
from app.models import DeployList, DeployRequest, DeployResponse, IdempotencyKeyHeader
from app.services import deploys

router = APIRouter(prefix="/deploys", tags=["deploys"])


@router.post("", response_model=DeployResponse, status_code=status.HTTP_201_CREATED)
async def record_deploy(
    body: DeployRequest,
    response: Response,
    pool: PoolDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> dict[str, Any]:
    """Record a fake deploy, so the investigation can ask "did something ship just before?"."""
    async with pool.connection() as conn:
        row, created = await deploys.create_deploy(
            conn, body.service, body.version, body.description, idempotency_key
        )
    if not created:
        response.status_code = status.HTTP_200_OK
    return row


@router.get("", response_model=DeployList)
async def list_deploys(
    pool: PoolDep,
    since_seconds: Annotated[int, Query(ge=1, le=7 * 24 * 3600)] = 3600,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> DeployList:
    async with pool.connection() as conn:
        rows = await deploys.list_deploys(conn, since_seconds, limit)
    return DeployList.model_validate({"deploys": rows})
