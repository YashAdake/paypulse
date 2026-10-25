import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app import temporal
from app.config import Settings
from app.errors import register_error_handlers
from app.log import configure_logging
from app.middleware import request_context
from app.routes import health, incidents, live

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    app.state.temporal = await temporal.connect(settings)
    async with httpx.AsyncClient(
        base_url=settings.payment_service_url, timeout=settings.http_timeout_s
    ) as payments:
        app.state.payments = payments
        log.info("api ready")
        yield
    log.info("api stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="PayPulse Command Center API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.middleware("http")(request_context)
    register_error_handlers(app)
    for module in (health, live, incidents):
        app.include_router(module.router)
    return app


app = create_app()
