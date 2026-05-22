# backend/core/kernel/domain/services.py
# Feladat: Custom domain application service-t valósít meg. Tenant domain overview-t épít, custom domaint ad hozzá, DNS verificationt futtat, törlést kezel és typed domain hibákat dob a router számára. Kernel domain service réteg, amely repository portokra, DomainPolicyra és verification portra épül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.domain.dto import DomainOverviewResponse, DomainRecordResponse
from core.kernel.domain.errors import (
    DomainNotFoundError,
    DomainPrimaryDeleteBlockedError,
    DomainTakenError,
    TenantNotFoundError,
)
from core.kernel.domain.ports import DomainRepositoryPort, DomainVerificationPort
from core.kernel.domain.policies import DomainPolicy


class DomainService:
    def __init__(
        self,
        repo: DomainRepositoryPort,
        policy: DomainPolicy,
        verification_service: DomainVerificationPort,
    ) -> None:
        self._repo = repo
        self._policy = policy
        self._verification_service = verification_service

    def _domain_record_response(self, domain, *, tenant_slug: str, tenant_id: int, is_primary: bool = False) -> DomainRecordResponse:  # type: ignore[no-untyped-def]
        state = "platform_primary" if is_primary else self._policy.classify_domain_state(domain, tenant_slug=tenant_slug)
        cname_target = self._verification_service.cname_target() if not is_primary else None
        dns_record_name, dns_record_value = self._verification_service.challenge_for_domain(domain.domain, tenant_id=tenant_id)
        return DomainRecordResponse(
            domain=domain.domain,
            state=state,
            verified_at=domain.verified_at.isoformat() if domain.verified_at else None,
            is_primary=is_primary,
            cname_target=cname_target,
            dns_record_type=None if is_primary else "TXT",
            dns_record_name=None if is_primary else dns_record_name,
            dns_record_value=None if is_primary else dns_record_value,
        )

    def get_overview(self, tenant_slug: str, active_domain) -> DomainOverviewResponse:
        tenant = self._repo.get_tenant_by_slug(tenant_slug)
        if tenant is None or tenant.tenant_id is None:
            raise TenantNotFoundError(tenant_slug)
        self._policy.ensure_tenant_domain_management_allowed(tenant.status)

        primary_host = self._policy.primary_host_for_slug(tenant.slug)
        domains = self._repo.list_domains_for_tenant(tenant.tenant_id)
        primary_record = next((domain for domain in domains if domain.domain == primary_host), None)
        primary_response = (
            self._domain_record_response(primary_record, tenant_slug=tenant.slug, tenant_id=tenant.tenant_id, is_primary=True)
            if primary_record is not None
            else DomainRecordResponse(
                domain=primary_host,
                state="platform_primary",
                verified_at=None,
                is_primary=True,
            )
        )
        custom_domains = tuple(
            self._domain_record_response(domain, tenant_slug=tenant.slug, tenant_id=tenant.tenant_id)
            for domain in domains
            if domain.domain != primary_host
        )
        return DomainOverviewResponse(
            tenant_slug=tenant.slug,
            primary_domain=primary_response,
            active_host=active_domain.request_host if active_domain else None,
            active_custom_domain=bool(active_domain and active_domain.is_custom_domain),
            custom_domains=custom_domains,
        )

    def add_custom_domain(
        self,
        tenant_slug: str,
        domain: str,
        *,
        actor_user_id: int | None = None,
    ) -> DomainRecordResponse:
        tenant = self._repo.get_tenant_by_slug(tenant_slug)
        if tenant is None or tenant.tenant_id is None:
            raise TenantNotFoundError(tenant_slug)
        self._policy.ensure_tenant_domain_management_allowed(tenant.status)
        normalized_domain = self._policy.normalize_custom_domain(domain)
        existing = self._repo.get_domain(normalized_domain)
        if existing is not None and existing.tenant_id != tenant.tenant_id:
            raise DomainTakenError(normalized_domain)
        created = self._repo.create_domain(tenant.tenant_id, normalized_domain, created_by=actor_user_id)
        return self._domain_record_response(created, tenant_slug=tenant.slug, tenant_id=tenant.tenant_id)

    def verify_custom_domain(
        self,
        tenant_slug: str,
        domain: str,
        *,
        actor_user_id: int | None = None,
    ) -> DomainRecordResponse:
        tenant = self._repo.get_tenant_by_slug(tenant_slug)
        if tenant is None or tenant.tenant_id is None:
            raise TenantNotFoundError(tenant_slug)
        self._policy.ensure_tenant_domain_management_allowed(tenant.status)
        normalized_domain = self._policy.normalize_custom_domain(domain)
        existing = self._repo.get_domain(normalized_domain)
        if existing is None or existing.tenant_id != tenant.tenant_id:
            raise DomainNotFoundError(normalized_domain)
        verified = self._verification_service.verify_domain(
            normalized_domain,
            tenant_id=tenant.tenant_id,
            actor_user_id=actor_user_id,
        )
        if verified is None:
            raise DomainNotFoundError(normalized_domain)
        return self._domain_record_response(verified, tenant_slug=tenant.slug, tenant_id=tenant.tenant_id)

    def delete_custom_domain(
        self,
        tenant_slug: str,
        domain: str,
    ) -> None:
        tenant = self._repo.get_tenant_by_slug(tenant_slug)
        if tenant is None or tenant.tenant_id is None:
            raise TenantNotFoundError(tenant_slug)
        self._policy.ensure_tenant_domain_management_allowed(tenant.status)
        normalized_domain = self._policy.normalize_custom_domain(domain)
        primary_host = self._policy.primary_host_for_slug(tenant.slug)
        if normalized_domain == primary_host:
            raise DomainPrimaryDeleteBlockedError()
        existing = self._repo.get_domain(normalized_domain)
        if existing is None or existing.tenant_id != tenant.tenant_id:
            raise DomainNotFoundError(normalized_domain)
        self._repo.delete_domain(normalized_domain, tenant_id=tenant.tenant_id)
