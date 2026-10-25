"""Every error leaves the service in one shape:
{"error": {"code": "...", "message": "...", "request_id": "...", "details": ...}}
"""

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from temporalio.service import RPCError, RPCStatusCode

from app.log import request_id_var
from app.payment_service import PaymentServiceError, PaymentServiceUnavailable

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
    return JSONResponse(
        status_code=422,
        content=error_body(
            "validation_error", "Request is invalid", jsonable_encoder(exc.errors())
        ),
    )


async def _payment_service_error(_: Request, exc: PaymentServiceError) -> JSONResponse:
    # payment-service already answers in our error shape: pass it through untouched.
    return JSONResponse(status_code=exc.status_code, content=exc.body)


async def _payment_service_unavailable(_: Request, exc: PaymentServiceUnavailable) -> JSONResponse:
    log.warning("payment-service unavailable", extra={"error": str(exc)})
    return JSONResponse(
        status_code=502,
        content=error_body("payment_service_unavailable", "payment-service is unreachable"),
    )


async def _temporal_error(_: Request, exc: RPCError) -> JSONResponse:
    if exc.status == RPCStatusCode.NOT_FOUND:
        return JSONResponse(
            status_code=404, content=error_body("not_found", "Incident not found or already closed")
        )
    log.warning("temporal call failed", extra={"status": exc.status.name, "error": exc.message})
    return JSONResponse(
        status_code=503, content=error_body("temporal_unavailable", "Temporal is unavailable")
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(PaymentServiceError, _payment_service_error)
    app.add_exception_handler(PaymentServiceUnavailable, _payment_service_unavailable)
    app.add_exception_handler(RPCError, _temporal_error)
