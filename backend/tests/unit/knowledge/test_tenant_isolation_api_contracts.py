from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.knowledge.api.router import router as knowledge_api_router
from apps.knowledge.dependencies import get_knowledge_facade
from apps.knowledge.domain.ingest_run import IngestRun
from core.kernel.http.correlation_id_middleware import CorrelationIdMiddleware
from core.kernel.http.exception_handlers import register_exception_handlers
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass(slots=True)
class _TenantRef:
    tenant_id: int
    slug: str


@dataclass(slots=True)
class _UserRef:
    user_id: int
    tenant: _TenantRef
    role: str = "user"

    @property
    def id(self) -> int:
        return self.user_id


@dataclass(slots=True)
class _KnowledgeBaseRef:
    uuid: str
    tenant: _TenantRef


def tenant_factory(*, tenant_id: int, slug: str) -> _TenantRef:
    return _TenantRef(tenant_id=tenant_id, slug=slug)


def user_factory(*, user_id: int, tenant: _TenantRef, role: str = "user") -> _UserRef:
    return _UserRef(user_id=user_id, tenant=tenant, role=role)


def knowledge_base_factory(*, uuid: str, tenant: _TenantRef) -> _KnowledgeBaseRef:
    return _KnowledgeBaseRef(uuid=uuid, tenant=tenant)


class _TenantIsolatedFacade:
    def __init__(self, *, run: IngestRun | None, readable_kb_uuids: set[str]) -> None:
        self._run = run
        self._readable_kb_uuids = set(readable_kb_uuids)

    def get_ingest_run(self, run_id: str) -> IngestRun | None:
        if self._run is None:
            return None
        return self._run if self._run.id == run_id else None

    def user_can_train(self, kb_uuid: str, user_id: int, user) -> bool:  # type: ignore[no-untyped-def]
        return kb_uuid in self._readable_kb_uuids

    def user_can_use(self, kb_uuid: str, user_id: int, user) -> bool:  # type: ignore[no-untyped-def]
        return kb_uuid in self._readable_kb_uuids

    async def build_chat_context(self, **_kwargs):  # type: ignore[no-untyped-def]
        return {}

    def enrich_ingest_items_with_document_metrics(self, items):  # type: ignore[no-untyped-def]
        return items

    def list_ingest_items(self, run_id: str):  # type: ignore[no-untyped-def]
        return []

    def list_ingest_events(self, run_id: str):  # type: ignore[no-untyped-def]
        return []

    def user_label(self, user_id):  # type: ignore[no-untyped-def]
        return None


def _build_client(*, facade: _TenantIsolatedFacade, tenant: _TenantRef, current_user: _UserRef) -> TestClient:
    app = FastAPI()
    app.include_router(knowledge_api_router, prefix="/api")
    app.dependency_overrides[get_knowledge_facade] = lambda: facade
    app.dependency_overrides[require_tenant_context] = lambda: SimpleNamespace(
        tenant_id=tenant.tenant_id,
        slug=tenant.slug,
        name=tenant.slug,
        created_at=datetime.now(timezone.utc),
        config=SimpleNamespace(package="starter", feature_flags={}, limits={}),
        status=None,
        domain=None,
        correlation_id="corr-tenant-test",
        security_version=0,
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=current_user.id,
        role=current_user.role,
        is_active=True,
    )
    return TestClient(app)


def _build_client_with_error_handlers(*, facade: _TenantIsolatedFacade, tenant: _TenantRef, current_user: _UserRef) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(knowledge_api_router, prefix="/api")
    app.dependency_overrides[get_knowledge_facade] = lambda: facade
    app.dependency_overrides[require_tenant_context] = lambda: SimpleNamespace(
        tenant_id=tenant.tenant_id,
        slug=tenant.slug,
        name=tenant.slug,
        created_at=datetime.now(timezone.utc),
        config=SimpleNamespace(package="starter", feature_flags={}, limits={}),
        status=None,
        domain=None,
        correlation_id="corr-tenant-test",
        security_version=0,
    )
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=current_user.id,
        role=current_user.role,
        is_active=True,
    )
    return TestClient(app)


def test_tenant_a_ingest_run_not_readable_from_tenant_b_returns_403() -> None:
    tenant_a = tenant_factory(tenant_id=101, slug="tenant-a")
    tenant_b = tenant_factory(tenant_id=202, slug="tenant-b")
    user_a = user_factory(user_id=11, tenant=tenant_a)
    kb_b = knowledge_base_factory(uuid="kb-tenant-b", tenant=tenant_b)
    run_b = IngestRun(
        id="run-tenant-b-1",
        tenant=tenant_b.slug,
        corpus_uuid=kb_b.uuid,
        status="processing",
        created_by=91,
    )
    facade = _TenantIsolatedFacade(run=run_b, readable_kb_uuids={"kb-tenant-a"})
    client = _build_client(facade=facade, tenant=tenant_a, current_user=user_a)

    response = client.get(f"/api/knowledge/ingest/runs/{run_b.id}")

    assert response.status_code == 403


def test_tenant_a_ingest_run_lookup_for_tenant_b_hidden_as_404() -> None:
    tenant_a = tenant_factory(tenant_id=101, slug="tenant-a")
    user_a = user_factory(user_id=11, tenant=tenant_a)
    facade = _TenantIsolatedFacade(run=None, readable_kb_uuids={"kb-tenant-a"})
    client = _build_client(facade=facade, tenant=tenant_a, current_user=user_a)

    response = client.get("/api/knowledge/ingest/runs/run-tenant-b-missing")

    assert response.status_code == 404


def test_knowledge_permission_denied_returns_safe_security_error_payload() -> None:
    tenant_a = tenant_factory(tenant_id=101, slug="tenant-a")
    user_a = user_factory(user_id=11, tenant=tenant_a)
    facade = _TenantIsolatedFacade(run=None, readable_kb_uuids=set())
    client = _build_client_with_error_handlers(facade=facade, tenant=tenant_a, current_user=user_a)

    response = client.post(
        "/api/knowledge/chat-context",
        json={"corpus_uuid": "kb-tenant-b", "query": "hello"},
        headers={"X-Request-ID": "req_knowledge_security"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "code": "PERMISSION_DENIED",
        "message": "You are not allowed to access this resource.",
        "request_id": "req_knowledge_security",
    }
