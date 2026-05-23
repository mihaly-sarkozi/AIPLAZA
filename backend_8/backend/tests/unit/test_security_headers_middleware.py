from __future__ import annotations

import asyncio

import pytest

from core.kernel.security.security_headers_middleware import SecurityHeadersMiddleware

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


def _ok_app(scope, receive, send):
    async def _impl():
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    return _impl()


def test_security_headers_present_on_http_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    wrapped = SecurityHeadersMiddleware(_ok_app)
    messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/livez",
                "scheme": "http",
                "headers": [],
            },
        )
    )
    headers = _header_map(messages)
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in headers
    assert "camera=()" in headers["permissions-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_hsts_set_only_for_production_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    wrapped = SecurityHeadersMiddleware(_ok_app)

    https_messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/livez",
                "scheme": "https",
                "headers": [],
            },
        )
    )
    https_headers = _header_map(https_messages)
    assert https_headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"

    http_messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/livez",
                "scheme": "http",
                "headers": [],
            },
        )
    )
    http_headers = _header_map(http_messages)
    assert "strict-transport-security" not in http_headers


def test_csp_not_overly_permissive_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    wrapped = SecurityHeadersMiddleware(_ok_app)
    messages = asyncio.run(
        _run_app(
            wrapped,
            {
                "type": "http",
                "method": "GET",
                "path": "/livez",
                "scheme": "https",
                "headers": [],
            },
        )
    )
    headers = _header_map(messages)
    csp = headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "* " not in csp
    assert "'unsafe-eval'" not in csp
