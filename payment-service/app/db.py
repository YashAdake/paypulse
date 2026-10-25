import asyncio
import logging
from pathlib import Path
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import Settings

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


async def wait_for_database(settings: Settings) -> None:
    """Retry a plain connection until Postgres accepts us.

    Done before opening the pool because a pool that fails to fill is closed for good
    and cannot be reopened.
    """
    for attempt in range(1, settings.db_startup_retries + 1):
        try:
            conn = await psycopg.AsyncConnection.connect(
                settings.database_url, connect_timeout=settings.db_connect_timeout_s
            )
            await conn.close()
            return
        except psycopg.OperationalError as exc:
            if attempt == settings.db_startup_retries:
                raise
            log.warning(
                "database not ready, retrying",
                extra={
                    "attempt": attempt,
                    "max_attempts": settings.db_startup_retries,
                    "error": str(exc),
                },
            )
            await asyncio.sleep(settings.db_startup_retry_delay_s)


async def open_pool(settings: Settings) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        timeout=settings.db_pool_timeout_s,
        kwargs={
            "connect_timeout": settings.db_connect_timeout_s,
            # Server-side cap so one slow query can't hold a connection forever.
            "options": f"-c statement_timeout={settings.db_statement_timeout_ms}",
            "row_factory": dict_row,
        },
        open=False,
    )
    await pool.open(wait=True, timeout=settings.db_connect_timeout_s * 2)
    return pool


async def apply_schema(pool: AsyncConnectionPool) -> None:
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    log.info("schema applied")


def get_pool(request: Request) -> AsyncConnectionPool:
    return request.app.state.pool


# Routes open `async with pool.connection()` themselves: the block commits on success
# and rolls back on error, before the response is sent.
PoolDep = Annotated[AsyncConnectionPool, Depends(get_pool)]
