from __future__ import annotations

import pytest
from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware

from core.kernel import app_factory
from core.platform.manifest import PlatformManifest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_register_middlewares_adds_slowapi_middleware(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    manifest = PlatformManifest(app_name="test")

    monkeypatch.setattr(app_factory, "get_token_service", lambda: object())
    monkeypatch.setattr(app_factory, "get_login_service", lambda: object())
    monkeypatch.setattr(app_factory, "get_tenant_repository", lambda: object())
    monkeypatch.setattr(app_factory, "get_service", lambda _key: object())

    app_factory._register_middlewares(app, manifest)  # type: ignore[attr-defined]

    assert any(middleware.cls is SlowAPIMiddleware for middleware in app.user_middleware)
