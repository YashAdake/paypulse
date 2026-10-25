from typing import Any

from fastapi import APIRouter

from app.db import PoolDep
from app.domain import Bank
from app.models import ChaosDeleteResponse, ChaosRuleList, ChaosRuleRequest, ChaosRuleResponse
from app.services import chaos

router = APIRouter(prefix="/chaos", tags=["chaos"])


@router.post("", response_model=ChaosRuleResponse)
async def set_rule(body: ChaosRuleRequest, pool: PoolDep) -> dict[str, Any]:
    """Break a bank on purpose. Replaces any existing rule for that bank."""
    async with pool.connection() as conn:
        return await chaos.upsert_rule(conn, body.bank, body.type, body.rate)


@router.get("", response_model=ChaosRuleList)
async def list_rules(pool: PoolDep) -> ChaosRuleList:
    async with pool.connection() as conn:
        rows = await chaos.list_rules(conn)
    return ChaosRuleList.model_validate({"rules": rows})


# Deletes return 200 with what was removed, never 404: the Phase 5 runbook clears chaos
# as its "fix", and Temporal may retry it after it already succeeded.
@router.delete("", response_model=ChaosDeleteResponse)
async def clear_all(pool: PoolDep) -> ChaosDeleteResponse:
    async with pool.connection() as conn:
        removed = await chaos.delete_rules(conn)
    return ChaosDeleteResponse.model_validate({"removed": removed})


@router.delete("/{bank}", response_model=ChaosDeleteResponse)
async def clear_bank(bank: Bank, pool: PoolDep) -> ChaosDeleteResponse:
    async with pool.connection() as conn:
        removed = await chaos.delete_rules(conn, bank)
    return ChaosDeleteResponse.model_validate({"removed": removed})
