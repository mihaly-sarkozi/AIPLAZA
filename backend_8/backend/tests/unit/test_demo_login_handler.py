from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request

from core.modules.auth.domain.dto.login_success_dto import LoginSuccess
from core.modules.auth.router import demo_login_handler
from core.modules.users.domain.dto.user import User

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/demo-login",
            "query_string": b"",
            "headers": [(b"accept-language", b"hu"), (b"user-agent", b"pytest")],
            "client": ("127.0.0.1", 12345),
            "server": ("demo.lvh.me", 8001),
            "scheme": "http",
        }
    )


def _tenant() -> SimpleNamespace:
    return SimpleNamespace(tenant_id=4, slug="demo", correlation_id="corr-1", security_version=0)


def _demo_user(*, credentials_password_set: bool = False) -> User:
    return User(
        id=1,
        email="demo@example.com",
        password_hash="placeholder",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=credentials_password_set,
    )


def test_handle_demo_login_success_issues_tokens_for_passwordless_demo_user() -> None:
    request = _request()
    response = Response()
    tenant = _tenant()
    user = _demo_user(credentials_password_set=False)

    svc = MagicMock()
    svc.user_repository.get_by_id.return_value = user
    svc.issue_tokens_for_user.return_value = LoginSuccess(
        access_token="access-123",
        refresh_token="refresh-456",
        user=user,
        access_jti="jti-1",
    )
    token_service = MagicMock()
    token_service.verify.return_value = {
        "typ": "demo_login",
        "tenant": "demo",
        "sub": "1",
        "email": "demo@example.com",
    }

    with patch.object(demo_login_handler, "build_token_response", return_value={"access_token": "access-123"}) as build_response:
        result = demo_login_handler.handle_demo_login(
            request=request,
            response=response,
            tenant=tenant,
            token="demo-token",
            svc=svc,
            token_service=token_service,
        )

    assert result == {"access_token": "access-123"}
    svc.issue_tokens_for_user.assert_called_once()
    call = svc.issue_tokens_for_user.call_args
    assert call.args[0] == user
    assert call.kwargs["auto_login"] is True
    assert call.kwargs["tenant"].slug == "demo"
    build_response.assert_called_once()


def test_handle_demo_login_success_even_when_password_already_set() -> None:
    request = _request()
    response = Response()
    tenant = _tenant()
    user = _demo_user(credentials_password_set=True)

    svc = MagicMock()
    svc.user_repository.get_by_id.return_value = user
    svc.issue_tokens_for_user.return_value = LoginSuccess(
        access_token="access-123",
        refresh_token="refresh-456",
        user=user,
        access_jti="jti-1",
    )
    token_service = MagicMock()
    token_service.verify.return_value = {
        "typ": "demo_login",
        "tenant": "demo",
        "sub": "1",
        "email": "demo@example.com",
    }

    with patch.object(demo_login_handler, "build_token_response", return_value={"access_token": "access-123"}):
        result = demo_login_handler.handle_demo_login(
            request=request,
            response=response,
            tenant=tenant,
            token="demo-token",
            svc=svc,
            token_service=token_service,
        )

    assert result == {"access_token": "access-123"}
    svc.issue_tokens_for_user.assert_called_once()


def test_handle_demo_login_rejects_email_mismatch() -> None:
    request = _request()
    response = Response()
    tenant = _tenant()
    user = _demo_user(credentials_password_set=False)

    svc = MagicMock()
    svc.user_repository.get_by_id.return_value = user
    token_service = MagicMock()
    token_service.verify.return_value = {
        "typ": "demo_login",
        "tenant": "demo",
        "sub": "1",
        "email": "other@example.com",
    }

    with pytest.raises(HTTPException) as exc:
        demo_login_handler.handle_demo_login(
            request=request,
            response=response,
            tenant=tenant,
            token="demo-token",
            svc=svc,
            token_service=token_service,
        )

    assert exc.value.status_code == 401
    assert exc.value.detail["reason"] == "invalid"
