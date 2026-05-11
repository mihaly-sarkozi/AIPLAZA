from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from core.extensions.tenant.dto import TenantDomainInfo, TenantStatus
from core.platform.brand.services import BrandService
from core.platform.domain.policies import DomainPolicy
from core.platform.domain.services import DomainService
from core.platform.lifecycle.services import LifecycleService


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

    def check_background_worker(self) -> str:
        return "running"


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
    assert readiness.checks["database"] == "ok"
    assert readiness.checks["cache"] == "ok"
    assert readiness.checks["background_worker"] == "running"
    assert health.status == "ok"
    assert status.startup_runs == 1
    assert status.startup_completed_at is not None


def test_domain_service_deletes_custom_domain():
    repo = _DomainRepoStub()
    service = DomainService(repo, DomainPolicy(tenant_base_domain="app.test"), _VerifyServiceStub())

    service.delete_custom_domain("acme", "portal.acme.test")

    assert repo.deleted == ["portal.acme.test"]
    assert all(item.domain != "portal.acme.test" for item in repo.domains)
