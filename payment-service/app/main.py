import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings
from app.db import apply_schema, open_pool, wait_for_database
from app.errors import register_error_handlers
from app.log import configure_logging
from app.middleware import request_context
from app.routes import chaos, deploys, health, payments, stats
from app.services.traffic import start_traffic, stop_traffic

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    await wait_for_database(settings)
    pool = await open_pool(settings)
    app.state.pool = pool
    traffic_task = None
    try:
        await apply_schema(pool)
        traffic_task = start_traffic(pool, settings.traffic_rps)
        log.info("payment-service ready")
        yield
    finally:
        # Stop traffic before closing the pool it writes through.
        await stop_traffic(traffic_task)
        await pool.close()
        log.info("payment-service stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="PayPulse payment-service", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.middleware("http")(request_context)
    register_error_handlers(app)
    for module in (health, payments, chaos, stats, deploys):
        app.include_router(module.router)
    return app


app = create_app()
