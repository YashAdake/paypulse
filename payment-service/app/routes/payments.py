from typing import Any

from fastapi import APIRouter, Response, status

from app.db import PoolDep
from app.models import IdempotencyKeyHeader, PaymentRequest, PaymentResponse
from app.services import payments

router = APIRouter(tags=["payments"])


@router.post("/pay", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def pay(
    body: PaymentRequest,
    response: Response,
    pool: PoolDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> dict[str, Any]:
    """Simulate one payment.

    A failed payment is still 201: the API call worked, the outcome is in `status`.
    A repeated Idempotency-Key returns the original payment with 200.
    """
    async with pool.connection() as conn:
        row, created = await payments.create_payment(
            conn, body.bank, body.method, body.amount_paise, idempotency_key
        )
    if not created:
        response.status_code = status.HTTP_200_OK
    return row
