import asyncio
import logging
from typing import Annotated

from fastapi import Depends, Request
from temporalio.client import Client

from app.config import Settings

log = logging.getLogger(__name__)


async def connect(settings: Settings) -> Client:
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


def get_client(request: Request) -> Client:
    return request.app.state.temporal


TemporalDep = Annotated[Client, Depends(get_client)]
