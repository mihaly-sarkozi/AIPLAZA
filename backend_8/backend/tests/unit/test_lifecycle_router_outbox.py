from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.kernel.lifecycle import lifecycle_router

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _LifecycleServiceStub:
    def outbox_snapshot(self):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            pending=12,
            running=2,
            failed=1,
            dead_letter=0,
            stuck_leases=0,
            oldest_pending_seconds=42.0,
            average_attempts=1.5,
            worker_status="running",
            worker_heartbeat_at="2026-05-22T10:00:00+00:00",
            worker_heartbeat_age_seconds=3.0,
        )


class _AuditStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def log(self, action, **kwargs):  # type: ignore[no-untyped-def]
        self.calls.append({"action": action, "kwargs": kwargs})


def _client_with_stub(monkeypatch: pytest.MonkeyPatch, *, authorized: bool) -> TestClient:
    app = FastAPI()
    app.include_router(lifecycle_router.router)
    app.dependency_overrides[lifecycle_router.get_lifecycle_service] = lambda: _LifecycleServiceStub()
    app.dependency_overrides[lifecycle_router.get_audit_service] = lambda: _AuditStub()
    monkeypatch.setattr(lifecycle_router, "_is_metrics_request_authorized", lambda _request, _token: authorized)
    return TestClient(app)


def test_internal_outbox_health_endpoint_returns_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with_stub(monkeypatch, authorized=True)

    response = client.get("/internal/health/outbox")

    assert response.status_code == 200
    payload = response.json()
    assert payload["pending"] == 12
    assert payload["running"] == 2
    assert payload["failed"] == 1
    assert payload["dead_letter"] == 0
    assert payload["stuck_leases"] == 0
    assert payload["oldest_pending_seconds"] == 42.0
    assert payload["average_attempts"] == 1.5
    assert payload["worker_status"] == "running"


def test_internal_outbox_health_endpoint_denies_unauthorized_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client_with_stub(monkeypatch, authorized=False)

    response = client.get("/internal/health/outbox")

    assert response.status_code == 404


def test_internal_routes_require_internal_admin_dependency_and_rate_limit() -> None:
    internal_routes = [
        route
        for route in lifecycle_router.router.routes
        if str(getattr(route, "path", "")).startswith("/internal/")
    ]

    assert internal_routes
    for route in internal_routes:
        dependency_calls = {
            getattr(dependency.call, "__name__", "")
            for dependency in getattr(getattr(route, "dependant", None), "dependencies", [])
        }
        assert "require_internal_admin" in dependency_calls
    source = Path("core/kernel/lifecycle/lifecycle_router.py").read_text(encoding="utf-8")
    assert '@router.get("/internal/health/outbox", response_model=OutboxSnapshotResponse)' in source
    assert '@limiter.limit("30/minute")' in source
