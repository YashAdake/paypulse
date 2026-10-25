from typing import Any

from psycopg import AsyncConnection

from app.domain import IdempotencyConflictError

_COLUMNS = "id, service, version, description, created_at"


async def create_deploy(
    conn: AsyncConnection,
    service: str,
    version: str,
    description: str | None,
    idempotency_key: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Record a fake deploy event. Returns (row, created); see payments.create_payment."""
    cur = await conn.execute(
        f"""
        INSERT INTO deploys (service, version, description, idempotency_key)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (idempotency_key) DO NOTHING
        RETURNING {_COLUMNS}
        """,
        (service, version, description, idempotency_key),
    )
    row = await cur.fetchone()
    if row is not None:
        return row, True

    cur = await conn.execute(
        f"SELECT {_COLUMNS} FROM deploys WHERE idempotency_key = %s", (idempotency_key,)
    )
    existing = await cur.fetchone()
    stored = (existing["service"], existing["version"], existing["description"])
    if stored != (service, version, description):
        raise IdempotencyConflictError("Idempotency-Key was already used for a different deploy")
    return existing, False


async def list_deploys(
    conn: AsyncConnection, since_seconds: int, limit: int
) -> list[dict[str, Any]]:
    cur = await conn.execute(
        f"""
        SELECT {_COLUMNS}
        FROM deploys
        WHERE created_at >= now() - make_interval(secs => %s)
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (since_seconds, limit),
    )
    return await cur.fetchall()
