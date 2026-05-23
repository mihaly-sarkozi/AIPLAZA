from __future__ import annotations

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_slowapi_middleware_enforces_route_limit() -> None:
    app = FastAPI()
    limiter = Limiter(key_func=get_remote_address)
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _handle_ratelimit(_request: Request, _exc: RateLimitExceeded):  # type: ignore[no-untyped-def]
        return JSONResponse(status_code=429, content={"detail": "rate_limited"})

    @app.get("/limited")
    @limiter.limit("1/minute")
    def _limited(request: Request):  # noqa: ARG001
        return {"ok": True}

    app.add_middleware(SlowAPIMiddleware)
    client = TestClient(app)

    first = client.get("/limited")
    second = client.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 429
