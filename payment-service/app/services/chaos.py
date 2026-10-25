from typing import Any

from psycopg import AsyncConnection

from app.domain import Bank, ChaosRule, ChaosType


async def upsert_rule(
    conn: AsyncConnection, bank: Bank, chaos_type: ChaosType, rate: float
) -> dict[str, Any]:
    # Upsert makes POST /chaos naturally idempotent: same body, same end state.
    cur = await conn.execute(
        """
        INSERT INTO chaos_rules (bank, type, rate)
        VALUES (%(bank)s, %(type)s, %(rate)s)
        ON CONFLICT (bank) DO UPDATE
            SET type = EXCLUDED.type, rate = EXCLUDED.rate, updated_at = now()
        RETURNING bank, type, rate, updated_at
        """,
        {"bank": bank, "type": chaos_type, "rate": rate},
    )
    return await cur.fetchone()


async def list_rules(conn: AsyncConnection) -> list[dict[str, Any]]:
    cur = await conn.execute("SELECT bank, type, rate, updated_at FROM chaos_rules ORDER BY bank")
    return await cur.fetchall()


async def get_rule(conn: AsyncConnection, bank: Bank) -> ChaosRule | None:
    cur = await conn.execute("SELECT type, rate FROM chaos_rules WHERE bank = %s", (bank,))
    row = await cur.fetchone()
    if row is None:
        return None
    return ChaosRule(bank=bank, type=ChaosType(row["type"]), rate=row["rate"])


async def delete_rules(conn: AsyncConnection, bank: Bank | None = None) -> list[str]:
    """Delete one bank's rule, or all rules when bank is None. Returns the banks removed."""
    if bank is None:
        cur = await conn.execute("DELETE FROM chaos_rules RETURNING bank")
    else:
        cur = await conn.execute("DELETE FROM chaos_rules WHERE bank = %s RETURNING bank", (bank,))
    return sorted(row["bank"] for row in await cur.fetchall())
