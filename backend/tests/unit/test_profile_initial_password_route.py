from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.modules.auth.domain.dto.login_success_dto import LoginSuccess
from core.modules.users.dependencies import get_user_service
from core.modules.users.domain.dto.user import User
from core.modules.users.router.profile_router import router
from core.kernel.deps.facade import get_login_service
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.tenant.dto.tenant_config import TenantConfig
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _user(*, credentials_password_set: bool = False) -> User:
    return User(
        id=1,
        email="demo@example.com",
        password_hash="placeholder-hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=credentials_password_set,
    )


def _tenant_context(*, demo_mode: bool) -> RequestTenantContext:
    return RequestTenantContext(
        tenant_id=4,
        slug="demo",
        name="Demo",
        created_at=datetime.now(timezone.utc),
        status=None,
        config=TenantConfig(tenant_id=4, slug="demo", package="free", feature_flags={"demo_mode": demo_mode}, limits={}),
        domain=None,
        correlation_id="corr-1",
        security_version=0,
    )


def _app(*, tenant: RequestTenantContext, current_user: User | None, user_service, login_service=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_tenant_context] = lambda: tenant
    app.dependency_overrides[get_user_service] = lambda: user_service
    app.dependency_overrides[get_login_service] = lambda: (login_service or MagicMock())
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return app


def test_set_initial_password_without_auth_returns_401() -> None:
    app = _app(
        tenant=_tenant_context(demo_mode=True),
        current_user=None,
        user_service=MagicMock(),
    )

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.post("/api/auth/me/set-initial-password", json={"new_password": "StrongPass1"})

    assert response.status_code == 401


def test_set_initial_password_success_returns_tokens_and_refresh_cookie() -> None:
    current_user = _user(credentials_password_set=False)
    updated_user = replace(current_user, credentials_password_set=True)

    user_service = MagicMock()
    user_service.set_initial_password_demo.return_value = None
    user_service.user_repository.get_by_id.return_value = updated_user

    login_service = MagicMock()
    login_service.issue_tokens_for_user.return_value = LoginSuccess(
        access_token="new-access-token",
        refresh_token="new-refresh-token",
        user=updated_user,
        access_jti="jti-123",
    )

    app = _app(
        tenant=_tenant_context(demo_mode=True),
        current_user=current_user,
        user_service=user_service,
        login_service=login_service,
    )

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.post("/api/auth/me/set-initial-password", json={"new_password": "StrongPass1"})

    assert response.status_code == 200
    data = response.json()
    assert data["access_token"] == "new-access-token"
    assert data["user"]["id"] == current_user.id
    assert "refresh_token=" in response.headers.get("set-cookie", "")
    user_service.set_initial_password_demo.assert_called_once_with(
        user_id=current_user.id,
        new_password="StrongPass1",
        tenant_demo_mode=True,
    )
    login_service.issue_tokens_for_user.assert_called_once()


def test_set_initial_password_credentials_already_set_returns_400() -> None:
    user_service = MagicMock()
    user_service.set_initial_password_demo.side_effect = ValueError("credentials_already_set")

    app = _app(
        tenant=_tenant_context(demo_mode=True),
        current_user=_user(credentials_password_set=False),
        user_service=user_service,
    )

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.post("/api/auth/me/set-initial-password", json={"new_password": "StrongPass1"})

    assert response.status_code == 400
    detail = response.json().get("detail", {})
    assert (
        (isinstance(detail, dict) and detail.get("code") == "credentials_already_set")
        or "jelszó" in str(detail).lower()
        or "already" in str(detail).lower()
    )


def test_set_initial_password_requires_demo_tenant() -> None:
    user_service = MagicMock()

    app = _app(
        tenant=_tenant_context(demo_mode=False),
        current_user=_user(credentials_password_set=False),
        user_service=user_service,
    )

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.post("/api/auth/me/set-initial-password", json={"new_password": "StrongPass1"})

    assert response.status_code == 403
