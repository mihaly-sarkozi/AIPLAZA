from __future__ import annotations

from core.platform.domain.dto import DomainOverviewResponse, DomainRecordResponse
from core.platform.domain.errors import DomainNotFoundError, DomainTakenError, TenantNotFoundError
from core.platform.domain.ports import DomainRepositoryPort, DomainVerificationPort
from core.platform.domain.policies import DomainPolicy


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

    def get_overview(self, tenant_slug: str, active_domain) -> DomainOverviewResponse:
        tenant = self._repo.get_tenant_by_slug(tenant_slug)
        if tenant is None or tenant.tenant_id is None:
            raise TenantNotFoundError(tenant_slug)
        self._policy.ensure_tenant_domain_management_allowed(tenant.status)

        primary_host = self._policy.primary_host_for_slug(tenant.slug)
        domains = self._repo.list_domains_for_tenant(tenant.tenant_id)
        primary_record = next((domain for domain in domains if domain.domain == primary_host), None)
        custom_domains = tuple(
            DomainRecordResponse(
                domain=domain.domain,
                state=self._policy.classify_domain_state(domain, tenant_slug=tenant.slug),
                verified_at=domain.verified_at.isoformat() if domain.verified_at else None,
                is_primary=False,
            )
            for domain in domains
            if domain.domain != primary_host
        )
        return DomainOverviewResponse(
            tenant_slug=tenant.slug,
            primary_domain=DomainRecordResponse(
                domain=primary_host,
                state="platform_primary",
                verified_at=primary_record.verified_at.isoformat() if primary_record and primary_record.verified_at else None,
                is_primary=True,
            ),
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
        return DomainRecordResponse(
            domain=created.domain,
            state=self._policy.classify_domain_state(created, tenant_slug=tenant.slug),
            verified_at=created.verified_at.isoformat() if created.verified_at else None,
            is_primary=False,
        )

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
        verified = self._verification_service.verify_domain(normalized_domain, actor_user_id=actor_user_id)
        if verified is None:
            raise DomainNotFoundError(normalized_domain)
        return DomainRecordResponse(
            domain=verified.domain,
            state=self._policy.classify_domain_state(verified, tenant_slug=tenant.slug),
            verified_at=verified.verified_at.isoformat() if verified.verified_at else None,
            is_primary=False,
        )
