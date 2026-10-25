"""Every error leaves the service in one shape:
{"error": {"code": "...", "message": "...", "request_id": "...", "details": ...}}
"""

import logging
from http import HTTPStatus
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import IdempotencyConflictError
from app.log import request_id_var

log = logging.getLogger(__name__)


def error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message, "request_id": request_id_var.get()}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _code_for(status: int) -> str:
    try:
        return HTTPStatus(status).phrase.lower().replace(" ", "_")
    except ValueError:
        return "error"


async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(_code_for(exc.status_code), str(exc.detail)),
        headers=exc.headers,
    )


async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # jsonable_encoder because pydantic error contexts can hold exception objects.
    return JSONResponse(
        status_code=422,
        content=error_body(
            "validation_error", "Request is invalid", jsonable_encoder(exc.errors())
        ),
    )


async def _idempotency_conflict(_: Request, exc: IdempotencyConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content=error_body("idempotency_conflict", str(exc)))


async def _database_unavailable(_: Request, exc: psycopg.OperationalError) -> JSONResponse:
    # Covers lost connections, statement timeouts and PoolTimeout (a subclass).
    # 503 tells callers (and Temporal retries later) this is temporary, not their fault.
    log.warning("database unavailable", extra={"error": str(exc)})
    return JSONResponse(
        status_code=503, content=error_body("database_unavailable", "Database is unavailable")
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(IdempotencyConflictError, _idempotency_conflict)
    app.add_exception_handler(psycopg.OperationalError, _database_unavailable)
