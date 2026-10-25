import asyncio
import contextlib
import logging
import random

from psycopg_pool import AsyncConnectionPool

from app.domain import Bank, Method, PaymentStatus
from app.services import payments

log = logging.getLogger(__name__)

_SUMMARY_EVERY_S = 30.0
_BANKS = list(Bank)
_METHODS = list(Method)


async def run_traffic(pool: AsyncConnectionPool, rps: float) -> None:
    """Create about `rps` random payments per second until cancelled.

    Calls the service layer directly rather than our own HTTP API: one less moving part.
    Logs a summary every 30s instead of one line per payment, which would bury other logs.
    """
    rng = random.Random()
    loop = asyncio.get_running_loop()
    interval = 1.0 / rps
    next_at = loop.time()
    summary_at = next_at + _SUMMARY_EVERY_S
    created = failed = errors = 0

    while True:
        try:
            async with pool.connection() as conn:
                row, _ = await payments.create_payment(
                    conn,
                    rng.choice(_BANKS),
                    rng.choice(_METHODS),
                    rng.randint(10_00, 5_000_00),  # ₹10 to ₹5,000
                )
            created += 1
            failed += row["status"] == PaymentStatus.FAILED
        except Exception:
            # Keep generating through DB blips; the error is logged, not hidden.
            errors += 1
            log.exception("traffic generator failed to create a payment")

        now = loop.time()
        if now >= summary_at:
            log.info(
                "traffic summary",
                extra={"payments": created, "failed": failed, "errors": errors, "rps": rps},
            )
            created = failed = errors = 0
            summary_at = now + _SUMMARY_EVERY_S

        # Schedule against a fixed clock so DB time doesn't slow the rate down,
        # but don't try to "catch up" after a long stall.
        next_at = max(next_at + interval, now)
        await asyncio.sleep(next_at - now)


def start_traffic(pool: AsyncConnectionPool, rps: float) -> asyncio.Task[None] | None:
    if rps <= 0:
        log.info("traffic generator disabled (TRAFFIC_RPS=0)")
        return None
    log.info("traffic generator started", extra={"rps": rps})
    return asyncio.create_task(run_traffic(pool, rps), name="traffic-generator")


async def stop_traffic(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
