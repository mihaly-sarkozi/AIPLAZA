from __future__ import annotations

import json
import logging
import asyncio

import pytest

from core.kernel.http.correlation_id_middleware import CorrelationIdMiddleware
from core.kernel.http.request_timing_middleware import RequestTimingMiddleware

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


async def _receive():
    return {"type": "http.request", "body": b"", "more_body": False}


async def _run_app(app, scope: dict) -> list[dict]:
    messages: list[dict] = []

    async def _send(message: dict) -> None:
        messages.append(message)

    await app(scope, _receive, _send)
    return messages


def _header_map(messages: list[dict]) -> dict[str, str]:
    response_start = next(msg for msg in messages if msg["type"] == "http.response.start")
    return {
        key.decode("latin-1").lower(): value.decode("latin-1")
        for key, value in response_start.get("headers", [])
    }


def test_correlation_middleware_uses_valid_inbound_headers():
    async def app(scope, receive, send):
        assert scope["state"]["correlation_id"] == "corr-12345678"
        assert scope["state"]["request_id"] == "req-12345678"
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    wrapped = CorrelationIdMiddleware(app)
    messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [
                    (b"x-correlation-id", b"corr-12345678"),
                    (b"x-request-id", b"req-12345678"),
                ],
            },
        )
    )

    headers = _header_map(messages)
    assert headers["x-correlation-id"] == "corr-12345678"
    assert headers["x-request-id"] == "req-12345678"


def test_correlation_middleware_generates_ids_for_invalid_inbound_values():
    async def app(scope, receive, send):
        assert scope["state"]["correlation_id"]
        assert scope["state"]["request_id"]
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    wrapped = CorrelationIdMiddleware(app)
    messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [(b"x-request-id", b"!bad!")],
            },
        )
    )

    headers = _header_map(messages)
    assert headers["x-request-id"]
    assert headers["x-correlation-id"]
    assert headers["x-request-id"] == headers["x-correlation-id"]
    assert headers["x-request-id"] != "!bad!"


def test_request_timing_middleware_logs_failed_request_with_context(caplog):
    async def failing_app(scope, receive, send):
        scope.setdefault("state", {})
        scope["state"]["request_id"] = "req-1"
        scope["state"]["tenant_slug"] = "demo"
        scope["state"]["tenant_id"] = 7
        scope["state"]["auth_outcome"] = "authenticated"
        scope["state"]["tenant_resolution_outcome"] = "resolved"
        raise RuntimeError("boom")

    wrapped = RequestTimingMiddleware(failing_app)

    with caplog.at_level(logging.ERROR, logger="core.request_timing"):
        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(
                _run_app(
                    wrapped,
                    {
                        "type": "http",
                        "method": "GET",
                        "path": "/api/test",
                        "headers": [],
                    },
                )
            )

    payload = json.loads(caplog.records[-1].message)
    assert payload["event_name"] == "request.failed"
    assert payload["request_id"] == "req-1"
    assert payload["tenant_slug"] == "demo"
    assert payload["tenant_id"] == 7
    assert payload["auth_outcome"] == "authenticated"
