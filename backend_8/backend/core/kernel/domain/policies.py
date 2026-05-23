# backend/core/kernel/domain/policies.py
# Feladat: Custom domain normalizálási, primary host és lifecycle engedélyezési policyt ad. A tenant routing policyra és tenant lifecycle policyra épít, hogy domain kezelés csak megfelelő tenant állapotban és konzisztens host szabályokkal történjen. Kernel domain-policy réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.dto import TenantDomain
from core.kernel.domain.errors import DomainManagementBlockedError
from core.modules.tenant.domain.tenant_policy import DomainRoutingPolicy, TenantLifecyclePolicy


class DomainPolicy:
    def __init__(
        self,
        *,
        tenant_base_domain: str,
        lifecycle_policy: TenantLifecyclePolicy | None = None,
        routing_policy: DomainRoutingPolicy | None = None,
    ):
        self._lifecycle_policy = lifecycle_policy or TenantLifecyclePolicy()
        self._routing_policy = routing_policy or DomainRoutingPolicy(tenant_base_domain=tenant_base_domain)

    def primary_host_for_slug(self, slug: str) -> str:
        return self._routing_policy.primary_host_for_slug(slug)

    def normalize_custom_domain(self, domain: str) -> str:
        return self._routing_policy.normalize_custom_domain(domain)

    def classify_domain_state(self, domain: TenantDomain, *, tenant_slug: str) -> str:
        return self._routing_policy.classify_domain_record(domain, tenant_slug=tenant_slug)

    def ensure_tenant_domain_management_allowed(self, tenant_status) -> None:
        state = self._lifecycle_policy.resolve_state(tenant_status)
        if state.status not in {TenantLifecyclePolicy.ACTIVE, TenantLifecyclePolicy.PROVISIONING}:
            raise DomainManagementBlockedError(state.status)
