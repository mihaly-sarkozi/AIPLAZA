from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from core.modules.tenant.dto import TenantDomainInfo, TenantStatus
from core.modules.brand.service.brand_service import BrandService
from core.kernel.domain.policies import DomainPolicy
from core.kernel.domain.services import DomainService
from core.kernel.lifecycle.lifecycle_service import LifecycleService


class _BrandRepoStub:
    def __init__(self, row=None):
        self._row = row
        self.updated = None

    def get_settings(self):
        return self._row

    def upsert_settings(self, **kwargs):
        self.updated = kwargs
        return SimpleNamespace(**kwargs)


class _DomainRepoStub:
    def __init__(self):
        self.tenant = SimpleNamespace(
            tenant_id=7,
            slug="acme",
            status=TenantStatus(tenant_id=7, slug="acme", is_active=True),
        )
        self.domains = [
            SimpleNamespace(domain="acme.app.test", verified_at=None, tenant_id=7),
            SimpleNamespace(domain="portal.acme.test", verified_at=datetime.now(timezone.utc), tenant_id=7),
        ]
        self.deleted: list[str] = []

    def get_tenant_by_slug(self, slug: str):
        return self.tenant if slug == "acme" else None

    def list_domains_for_tenant(self, tenant_id: int):
        return self.domains

    def get_domain(self, domain: str):
        return next((item for item in self.domains if item.domain == domain), None)

    def create_domain(self, tenant_id: int, domain: str, *, created_by=None):
        row = SimpleNamespace(domain=domain, verified_at=None, tenant_id=tenant_id)
        self.domains.append(row)
        return row

    def delete_domain(self, domain: str, *, tenant_id=None):
        self.deleted.append(domain)
        self.domains = [item for item in self.domains if item.domain != domain]


class _VerifyServiceStub:
    def verify_domain(self, domain: str, *, tenant_id: int, actor_user_id=None):
        return SimpleNamespace(domain=domain, verified_at=datetime.now(timezone.utc))

    def challenge_for_domain(self, domain: str, *, tenant_id: int):
        return (f"_aiplaza-challenge.{domain}", f"token-{tenant_id}")

    def cname_target(self) -> str:
        return "app.test"


class _LifecycleProbeStub:
    def check_database(self) -> str:
        return "ok"

    def check_cache(self) -> str:
        return "ok"

    def check_redis(self) -> str:
        return "ok"

    def check_object_storage(self) -> str:
        return "ok"

    def check_migrations(self) -> str:
        return "ok"

    def check_url_ingest_isolation_guard(self) -> str:
        return "ok"

    def check_outbox_queue(self) -> str:
        return "ok"

    def check_smtp(self) -> str:
        return "ok"

    def check_background_worker(self) -> str:
        return "running"

    def outbox_queue_snapshot(self) -> dict[str, object]:
        return {
            "pending": 12,
            "running": 2,
            "failed": 1,
            "dead_letter": 0,
            "stuck_leases": 0,
            "oldest_pending_seconds": 42.0,
            "average_attempts": 1.5,
            "worker_status": "running",
            "worker_heartbeat_at": "2026-05-22T10:00:00+00:00",
            "worker_heartbeat_age_seconds": 3.0,
        }


def test_brand_service_returns_defaults_without_row():
    service = BrandService(_BrandRepoStub())

    result = service.get_brand()

    assert result.display_name == ""
    assert result.primary_color == "#2563eb"
    assert result.public_enabled is True


def test_domain_service_returns_primary_and_custom_domains():
    service = DomainService(_DomainRepoStub(), DomainPolicy(tenant_base_domain="app.test"), _VerifyServiceStub())

    result = service.get_overview(
        "acme",
        TenantDomainInfo(
            request_host="portal.acme.test",
            resolved_host="portal.acme.test",
            is_custom_domain=True,
            verified_at=datetime.now(timezone.utc),
        ),
    )

    assert result.tenant_slug == "acme"
    assert result.primary_domain.domain == "acme.app.test"
    assert result.primary_domain.state == "platform_primary"
    assert result.active_custom_domain is True
    assert len(result.custom_domains) == 1
    assert result.custom_domains[0].domain == "portal.acme.test"
    assert result.custom_domains[0].state == "custom_verified"


def test_domain_policy_rejects_platform_domain():
    policy = DomainPolicy(tenant_base_domain="app.test")

    try:
        policy.normalize_custom_domain("demo.app.test")
    except ValueError as exc:
        assert str(exc) == "platform_domain_reserved"
    else:
        raise AssertionError("Expected platform domain to be rejected")


def test_lifecycle_service_tracks_startup_and_readiness():
    service = LifecycleService(probe_repository=_LifecycleProbeStub())

    service.mark_startup_begin()
    service.mark_startup_complete()
    liveness = service.liveness()
    readiness = service.readiness()
    health = service.health()
    status = service.runtime_status()

    assert liveness.status == "alive"
    assert liveness.startup_completed is True
    assert readiness.status == "ready"
    assert readiness.checks["startup"] == "ok"
    assert readiness.checks["db"] == "ok"
    assert readiness.checks["cache"] == "ok"
    assert readiness.checks["redis"] == "ok"
    assert readiness.checks["object_storage"] == "ok"
    assert readiness.checks["migrations"] == "ok"
    assert readiness.checks["url_ingest_isolation"] == "ok"
    assert readiness.checks["outbox"] == "ok"
    assert readiness.checks["smtp"] == "ok"
    assert readiness.checks["outbox_worker"] == "running"
    assert health.status == "ok"
    assert status.startup_runs == 1
    assert status.startup_completed_at is not None
    outbox = service.outbox_snapshot()
    assert outbox.pending == 12
    assert outbox.running == 2
    assert outbox.oldest_pending_seconds == 42.0
    assert outbox.worker_status == "running"


def test_lifecycle_service_reports_degraded_when_critical_dependency_fails(monkeypatch):
    class _Probe(_LifecycleProbeStub):
        def check_migrations(self) -> str:
            raise RuntimeError("migrations_missing:abc123")

    monkeypatch.setenv("APP_ENV", "production")
    service = LifecycleService(probe_repository=_Probe())
    service.mark_startup_begin()
    service.mark_startup_complete()

    readiness = service.readiness()

    assert readiness.status == "degraded"
    assert str(readiness.checks["migrations"]).startswith("error:")


def test_domain_service_deletes_custom_domain():
    repo = _DomainRepoStub()
    service = DomainService(repo, DomainPolicy(tenant_base_domain="app.test"), _VerifyServiceStub())

    service.delete_custom_domain("acme", "portal.acme.test")

    assert repo.deleted == ["portal.acme.test"]
    assert all(item.domain != "portal.acme.test" for item in repo.domains)
