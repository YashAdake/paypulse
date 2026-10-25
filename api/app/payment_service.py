"""Thin client for payment-service. The api only relays; payment-service does the maths."""

from typing import Annotated, Any

import httpx
from fastapi import Depends, Request


class PaymentServiceError(Exception):
    """payment-service answered with an error; relay its status and body."""

    def __init__(self, status_code: int, body: Any) -> None:
        super().__init__(f"payment-service returned {status_code}")
        self.status_code = status_code
        self.body = body


class PaymentServiceUnavailable(Exception):
    """payment-service could not be reached at all (down, timeout)."""


async def call(http: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> Any:
    try:
        resp = await http.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise PaymentServiceUnavailable(str(exc)) from exc
    if resp.is_error:
        try:
            body = resp.json()
        except ValueError:
            body = {"error": {"code": "upstream_error", "message": resp.text[:300]}}
        raise PaymentServiceError(resp.status_code, body)
    return resp.json()


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.payments


PaymentsDep = Annotated[httpx.AsyncClient, Depends(get_http)]
