from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.knowledge.api.router import router as knowledge_api_router
from apps.knowledge.bootstrap.dependencies import get_knowledge_facade
from apps.knowledge.service.url_ingest_security import UrlIngestSecurityError
from core.kernel.http.exception_handlers import register_exception_handlers
from core.kernel.http.correlation_id_middleware import CorrelationIdMiddleware
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _FacadeRejectingUrlIngest:
    def user_can_train(self, kb_uuid: str, user_id: int, user) -> bool:  # type: ignore[no-untyped-def]
        return True

    def create_url_ingest_run(self, **_kwargs):  # type: ignore[no-untyped-def]
        raise UrlIngestSecurityError("PRIVATE_IP_BLOCKED", "The provided URL is not allowed.")


def test_url_ingest_returns_machine_readable_code_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.knowledge.api.upload_support.settings.training_mfa_required", False, raising=False)
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(knowledge_api_router, prefix="/api")
    app.dependency_overrides[get_knowledge_facade] = lambda: _FacadeRejectingUrlIngest()
    app.dependency_overrides[require_tenant_context] = lambda: SimpleNamespace(
        tenant_id=10,
        slug="demo",
        name="Demo",
        created_at=datetime.now(timezone.utc),
        config=SimpleNamespace(package="starter", feature_flags={}, limits={}),
        status=None,
        domain=None,
        correlation_id="corr-url-ingest",
        security_version=0,
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=11, role="owner", is_active=True)

    client = TestClient(app, base_url="http://demo.app.test")
    response = client.post(
        "/api/knowledge/corpora/kb-1/ingest/urls",
        json={"items": [{"url": "http://127.0.0.1/private"}]},
        headers={"X-Request-ID": "req_url_1234"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["code"] == "PRIVATE_IP_BLOCKED"
    assert payload["message"] == "The provided URL is not allowed."
    assert payload["request_id"] == "req_url_1234"
