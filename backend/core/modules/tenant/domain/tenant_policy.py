# backend/core/modules/tenant/domain/tenant_policy.py
# Feladat: Tenant lifecycle és domain routing policykat tartalmaz. Tenant státuszból lifecycle állapotot számol, host/domain normalizálást és primary/custom domain osztályozást végez. Tenant domain policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.modules.tenant.dto import TenantDomain, TenantSnapshot, TenantStatus


@dataclass(frozen=True)
class TenantLifecycleState:
    status: str
    is_routable: bool
    can_activate: bool
    can_suspend: bool


@dataclass(frozen=True)
class DomainRoutingDecision:
    tenant_slug: str | None
    is_custom_domain: bool
    is_routable: bool
    lifecycle_state: str
    reason: str


class TenantLifecyclePolicy:
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"

    # Ez a metódus feloldja a(z) állapot logikáját.
    def resolve_state(self, status: TenantStatus | None) -> TenantLifecycleState:
        if status is None:
            return TenantLifecycleState(status=self.PROVISIONING, is_routable=False, can_activate=False, can_suspend=False)
        if status.is_active:
            return TenantLifecycleState(status=self.ACTIVE, is_routable=True, can_activate=False, can_suspend=True)
        if status.suspended_reason:
            return TenantLifecycleState(status=self.SUSPENDED, is_routable=False, can_activate=True, can_suspend=False)
        return TenantLifecycleState(status=self.PROVISIONING, is_routable=False, can_activate=True, can_suspend=False)

    # Ez a metódus a(z) assert_transition logikáját valósítja meg.
    def assert_transition(self, current_status: TenantStatus | None, target_state: str) -> None:
        current = self.resolve_state(current_status)
        normalized_target = (target_state or "").strip().lower()
        if normalized_target == self.ACTIVE and current.can_activate:
            return
        if normalized_target == self.SUSPENDED and current.can_suspend:
            return
        raise ValueError(f"invalid_tenant_transition:{current.status}->{normalized_target}")

    # Ez a metódus a(z) assert_routable logikáját valósítja meg.
    def assert_routable(self, snapshot: TenantSnapshot) -> None:
        current = self.resolve_state(snapshot.status)
        if not current.is_routable:
            raise ValueError(f"tenant_not_routable:{current.status}")


class DomainRoutingPolicy:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, *, tenant_base_domain: str, localhost_tenant: str | None = "demo") -> None:
        self._tenant_base_domain = (tenant_base_domain or "").strip().lower()
        self._localhost_tenant = (localhost_tenant or "").strip().lower() or None

    # Ez a metódus a(z) primary_host_for_slug logikáját valósítja meg.
    def primary_host_for_slug(self, slug: str) -> str:
        return f"{slug}.{self._tenant_base_domain}"

    # Ez a metódus normalizálja a(z) custom domain logikáját.
    def normalize_custom_domain(self, domain: str) -> str:
        normalized = (domain or "").strip().lower()
        if not normalized:
            raise ValueError("domain_required")
        if normalized == self._tenant_base_domain or normalized.endswith("." + self._tenant_base_domain):
            raise ValueError("platform_domain_reserved")
        return normalized

    # Ez a metódus a(z) host_kind logikáját valósítja meg.
    def host_kind(self, host: str) -> str:
        normalized = (host or "").strip().lower()
        if not normalized:
            return "missing"
        if normalized == self._tenant_base_domain:
            return "platform_root"
        if normalized.endswith("." + self._tenant_base_domain):
            return "platform_subdomain"
        if self._localhost_tenant and normalized in {"localhost", "127.0.0.1"}:
            return "localhost"
        return "custom_domain"

    # Ez a metódus feloldja a(z) platform slug logikáját.
    def resolve_platform_slug(self, host: str) -> str | None:
        kind = self.host_kind(host)
        normalized = (host or "").strip().lower()
        if kind == "platform_subdomain":
            return normalized[: -len(self._tenant_base_domain) - 1].strip().lower() or None
        if kind == "localhost":
            return self._localhost_tenant
        return None

    # Ez a metódus a(z) classify_domain_record logikáját valósítja meg.
    def classify_domain_record(self, domain: TenantDomain, *, tenant_slug: str) -> str:
        normalized = (domain.domain or "").strip().lower()
        if normalized == self.primary_host_for_slug(tenant_slug):
            return "platform_primary"
        if domain.verified_at is not None:
            return "custom_verified"
        return "custom_pending"

    # Ez a metódus a(z) route_for_platform_host logikáját valósítja meg.
    def route_for_platform_host(self, host: str, tenant_slug: str | None) -> DomainRoutingDecision:
        return DomainRoutingDecision(
            tenant_slug=tenant_slug,
            is_custom_domain=False,
            is_routable=tenant_slug is not None,
            lifecycle_state="platform_host",
            reason="platform_host_resolved" if tenant_slug else "platform_host_missing_slug",
        )

    # Ez a metódus a(z) route_for_custom_domain logikáját valósítja meg.
    def route_for_custom_domain(self, domain: TenantDomain | None) -> DomainRoutingDecision:
        if domain is None:
            return DomainRoutingDecision(
                tenant_slug=None,
                is_custom_domain=True,
                is_routable=False,
                lifecycle_state="missing",
                reason="custom_domain_not_found",
            )
        state = "verified" if domain.verified_at is not None else "pending_verification"
        return DomainRoutingDecision(
            tenant_slug=str(domain.tenant_id),
            is_custom_domain=True,
            is_routable=domain.verified_at is not None,
            lifecycle_state=state,
            reason="custom_domain_verified" if domain.verified_at is not None else "custom_domain_unverified",
        )


__all__ = [
    "DomainRoutingDecision",
    "DomainRoutingPolicy",
    "TenantLifecyclePolicy",
    "TenantLifecycleState",
]
