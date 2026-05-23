from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.kernel.security.csrf_middleware import CSRFMiddleware

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


async def _ok(_request):
    return JSONResponse({"ok": True})


def _app_with_csrf() -> TestClient:
    app = Starlette(
        routes=[
            Route("/api/platform-admin/auth/refresh", _ok, methods=["POST"]),
            Route("/api/platform-admin/auth/login", _ok, methods=["POST"]),
            Route("/api/channel/chat", _ok, methods=["POST"]),
        ]
    )
    app.add_middleware(CSRFMiddleware)
    return TestClient(app)


def test_platform_admin_refresh_is_csrf_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_CSRF", "0")
    client = _app_with_csrf()

    response = client.post("/api/platform-admin/auth/refresh")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_platform_admin_csrf_uses_dedicated_cookie_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_CSRF", "0")
    client = _app_with_csrf()
    token = "abc123"

    client.cookies.set("csrf_token", token)
    wrong_cookie_response = client.post(
        "/api/platform-admin/auth/login",
        headers={"X-CSRF-Token": token},
    )
    assert wrong_cookie_response.status_code == 403

    client.cookies.clear()
    client.cookies.set("platform_admin_csrf_token", token)
    ok_response = client.post(
        "/api/platform-admin/auth/login",
        headers={"X-CSRF-Token": token},
    )
    assert ok_response.status_code == 200
    assert ok_response.json() == {"ok": True}


def test_channel_bearer_request_is_csrf_exempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_CSRF", "0")
    client = _app_with_csrf()

    response = client.post(
        "/api/channel/chat",
        headers={"Authorization": "Bearer demo_channel_secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_channel_request_without_api_credential_still_requires_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DISABLE_CSRF", "0")
    client = _app_with_csrf()

    response = client.post("/api/channel/chat")

    assert response.status_code == 403
