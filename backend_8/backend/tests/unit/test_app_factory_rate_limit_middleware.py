from __future__ import annotations

import pytest
from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware

from core.kernel.http import middleware_registration
from core.kernel.app.app_manifest import AppManifest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_register_middlewares_adds_slowapi_middleware(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    manifest = AppManifest(app_name="test")

    monkeypatch.setattr(middleware_registration, "get_token_service", lambda: object())
    monkeypatch.setattr(middleware_registration, "get_login_service", lambda: object())
    monkeypatch.setattr(middleware_registration, "get_tenant_repository", lambda: object())
    monkeypatch.setattr(middleware_registration, "get_service", lambda _key: object())

    middleware_registration.register_middlewares(app, manifest)

    assert any(middleware.cls is SlowAPIMiddleware for middleware in app.user_middleware)
