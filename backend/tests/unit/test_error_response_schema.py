from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from core.kernel.http.correlation_id_middleware import CorrelationIdMiddleware
from core.kernel.http.app_errors import AppError, ErrorMapper, KnowledgeBaseNotFound, TenantAccessDenied
from core.kernel.http.error_payloads import build_error_payload
from core.kernel.http.exception_handlers import register_exception_handlers
from core.kernel.security.errors import security_http_exception
from apps.chat.errors import ChannelCredentialRejected, ChatPermissionDenied, ChatRequestInvalid

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)
    return app


def test_http_exception_returns_unified_error_schema_with_request_id() -> None:
    app = _app()

    @app.get("/secure")
    def _secure():  # type: ignore[no-untyped-def]
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials"})

    client = TestClient(app)
    response = client.get("/secure", headers={"X-Request-ID": "req_12345678"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == "invalid_credentials"
    assert payload["message"]
    assert payload["request_id"] == "req_12345678"
    assert isinstance(payload["detail"], dict)
    assert payload["detail"]["code"] == "invalid_credentials"


def test_sensitive_security_error_does_not_expose_internal_reason() -> None:
    app = _app()

    @app.get("/channel")
    def _channel():  # type: ignore[no-untyped-def]
        raise HTTPException(status_code=401, detail="invalid_signature: hmac mismatch for nonce")

    client = TestClient(app)
    response = client.get("/channel", headers={"X-Request-ID": "req_abcdefgh"})

    assert response.status_code == 401
    payload = response.json()
    assert payload["code"] == "UNAUTHORIZED"
    assert payload["message"] == "Authentication failed."
    assert payload["detail"] == "Authentication failed."
    assert "details" not in payload


def test_security_http_exception_returns_minimal_safe_payload() -> None:
    app = _app()

    @app.get("/permission")
    def _permission():  # type: ignore[no-untyped-def]
        raise security_http_exception()

    client = TestClient(app)
    response = client.get("/permission", headers={"X-Request-ID": "req_security1"})

    assert response.status_code == 403
    assert response.json() == {
        "code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this resource.",
        "request_id": "req_security1",
    }


def test_security_http_exception_can_return_safe_auth_failure() -> None:
    app = _app()

    @app.get("/auth")
    def _auth():  # type: ignore[no-untyped-def]
        raise security_http_exception(status_code=401, code="UNAUTHORIZED", message="Authentication failed.")

    client = TestClient(app)
    response = client.get("/auth", headers={"X-Request-ID": "req_security2"})

    assert response.status_code == 401
    assert response.json() == {
        "code": "UNAUTHORIZED",
        "message": "Authentication failed.",
        "request_id": "req_security2",
    }


def test_app_error_returns_unified_safe_payload_with_request_id() -> None:
    app = _app()

    @app.get("/tenant")
    def _tenant():  # type: ignore[no-untyped-def]
        raise TenantAccessDenied()

    client = TestClient(app)
    response = client.get("/tenant", headers={"X-Request-ID": "req_app_error1"})

    assert response.status_code == 403
    assert response.json() == {
        "code": "TENANT_ACCESS_DENIED",
        "message": "You are not allowed to access this tenant.",
        "request_id": "req_app_error1",
    }


def test_app_error_safe_details_are_explicit_only() -> None:
    mapped = ErrorMapper().to_response_payload(
        AppError(
            "Safe public message.",
            code="PUBLIC_FAILURE",
            status_code=400,
            safe_details={"field": "url"},
        ),
        request_id="req_mapper1",
    )

    assert mapped.status_code == 400
    assert mapped.payload == {
        "code": "PUBLIC_FAILURE",
        "message": "Safe public message.",
        "request_id": "req_mapper1",
        "details": {"field": "url"},
    }


def test_knowledge_base_not_found_app_error_schema() -> None:
    app = _app()

    @app.get("/kb")
    def _kb():  # type: ignore[no-untyped-def]
        raise KnowledgeBaseNotFound()

    client = TestClient(app)
    response = client.get("/kb", headers={"X-Request-ID": "req_kb_404"})

    assert response.status_code == 404
    assert response.json()["code"] == "KNOWLEDGE_BASE_NOT_FOUND"
    assert response.json()["request_id"] == "req_kb_404"


def test_module_specific_app_errors_map_to_unified_schema() -> None:
    app = _app()

    @app.get("/chat-denied")
    def _chat_denied():  # type: ignore[no-untyped-def]
        raise ChatPermissionDenied()

    @app.get("/channel-credential")
    def _channel_credential():  # type: ignore[no-untyped-def]
        raise ChannelCredentialRejected()

    @app.get("/chat-request-invalid")
    def _chat_request_invalid():  # type: ignore[no-untyped-def]
        raise ChatRequestInvalid()

    client = TestClient(app)

    assert client.get("/chat-denied").json()["code"] == "CHAT_PERMISSION_DENIED"
    response = client.get("/channel-credential")
    assert response.status_code == 401
    assert response.json()["code"] == "CHANNEL_CREDENTIAL_REJECTED"
    assert client.get("/chat-request-invalid").json()["code"] == "CHAT_REQUEST_INVALID"


def test_build_error_payload_strips_stack_details_in_production(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")

    payload = build_error_payload(
        status_code=500,
        request_id="req_stack_1",
        detail={"traceback": "boom", "reason": "failure"},
    )

    assert payload["code"] == "INTERNAL_ERROR"
    assert payload["message"] == "Internal server error."
    assert payload["request_id"] == "req_stack_1"
    assert "details" not in payload
    assert payload["detail"] == "Internal server error."
