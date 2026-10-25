"""Worker process: runs the Temporal worker (workflow + activities) and the detector loop."""

import asyncio
import contextlib
import logging
import signal

import httpx
from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import Activities
from app.config import Settings
from app.detector import Detector
from app.log import configure_logging
from app.workflows import InvestigateIncident

log = logging.getLogger(__name__)


async def connect_temporal(settings: Settings) -> Client:
    # Temporal may still be starting when this container comes up.
    for attempt in range(1, settings.temporal_connect_retries + 1):
        try:
            return await Client.connect(
                settings.temporal_address, namespace=settings.temporal_namespace
            )
        except Exception as exc:  # the SDK raises a plain RuntimeError on connect failure
            if attempt == settings.temporal_connect_retries:
                raise
            log.warning(
                "temporal not ready, retrying",
                extra={"attempt": attempt, "address": settings.temporal_address, "error": str(exc)},
            )
            await asyncio.sleep(settings.temporal_connect_retry_delay_s)
    raise AssertionError("unreachable")


async def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    client = await connect_temporal(settings)

    async with (
        httpx.AsyncClient(
            base_url=settings.payment_service_url, timeout=settings.http_timeout_s
        ) as payments,
        httpx.AsyncClient(
            base_url=settings.llm_base_url,
            timeout=settings.llm_timeout_s,
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        ) as llm,
        httpx.AsyncClient(
            base_url=settings.supermemory_base_url,
            timeout=settings.http_timeout_s * 4,
            headers={"Authorization": f"Bearer {settings.supermemory_api_key}"},
        ) as memory,
    ):
        acts = Activities(settings, payments, llm, memory)
        worker = Worker(
            client,
            task_queue=settings.task_queue,
            workflows=[InvestigateIncident],
            activities=[
                acts.gather_evidence,
                acts.recall_memory,
                acts.analyze_root_cause,
                acts.notify,
                acts.run_runbook,
                acts.check_bank_health,
                acts.save_memory,
            ],
        )

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        async with worker:
            detector = asyncio.create_task(Detector(client, payments, settings).run())
            log.info(
                "worker ready",
                extra={
                    "task_queue": settings.task_queue,
                    "llm_configured": bool(settings.llm_api_key),
                    "llm_model": settings.llm_model,
                    "supermemory_configured": bool(settings.supermemory_api_key),
                },
            )
            await stop.wait()
            detector.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await detector
    log.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
