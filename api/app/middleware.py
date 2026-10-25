import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.errors import error_body
from app.log import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

log = logging.getLogger("paypulse.access")


async def request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Tag every request with an ID, write one access log line, and turn crashes into JSON 500s.

    Unexpected exceptions are caught here (not in an exception handler) because handlers
    for bare Exception run outside this middleware, after the request ID is gone.
    """
    # Reuse the caller's ID so a request can be traced across services.
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled error")
            response = JSONResponse(
                status_code=500, content=error_body("internal_error", "Internal server error")
            )
        response.headers[REQUEST_ID_HEADER] = request_id
        # The UI polls several GETs per second; log only changes (POST/DELETE) and errors at INFO.
        quiet = request.method == "GET" and response.status_code < 400
        level = logging.DEBUG if quiet else logging.INFO
        log.log(
            level,
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response
    finally:
        request_id_var.reset(token)
