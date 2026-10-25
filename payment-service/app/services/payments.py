import random
from typing import Any

from psycopg import AsyncConnection

from app.domain import Bank, IdempotencyConflictError, Method
from app.services import chaos
from app.services.simulator import simulate

_rng = random.Random()

_COLUMNS = "id, bank, method, amount_paise, status, error_code, latency_ms, created_at"


async def create_payment(
    conn: AsyncConnection,
    bank: Bank,
    method: Method,
    amount_paise: int,
    idempotency_key: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Simulate and store one payment. Returns (row, created).

    created is False when the Idempotency-Key was seen before: the stored payment is
    returned instead of charging twice.
    """
    rule = await chaos.get_rule(conn, bank)
    outcome = simulate(bank, method, rule, _rng)
    cur = await conn.execute(
        f"""
        INSERT INTO payments
            (bank, method, amount_paise, status, error_code, latency_ms, idempotency_key)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING {_COLUMNS}
        """,
        (
            bank,
            method,
            amount_paise,
            outcome.status,
            outcome.error_code,
            outcome.latency_ms,
            idempotency_key,
        ),
    )
    row = await cur.fetchone()
    if row is not None:
        return row, True

    # Key already used: the outcome rolled above is discarded.
    cur = await conn.execute(
        f"SELECT {_COLUMNS} FROM payments WHERE idempotency_key = %s", (idempotency_key,)
    )
    existing = await cur.fetchone()
    stored = (existing["bank"], existing["method"], existing["amount_paise"])
    if stored != (bank, method, amount_paise):
        raise IdempotencyConflictError("Idempotency-Key was already used for a different payment")
    return existing, False
