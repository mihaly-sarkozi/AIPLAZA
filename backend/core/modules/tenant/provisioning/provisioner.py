# backend/core/modules/tenant/provisioning/provisioner.py
# Feladat: Új tenant provisioning folyamatot vezénylő service. Tenant schema, tenant rekord, config, domain, user és extension hook inicializálást köt össze kompenzációval részleges hibák esetére. Kritikus tenant létrehozási use case.
# Sárközi Mihály - 2026.05.21

"""Tenant provisioning service.

Responsibility: idempotently create all artefacts for a new tenant (schema,
tenant row, owner user, actor, config, domains, activation) and compensate on
failure.  Each step is a separate _ensure_* method to make the logic auditable
and testable in isolation.
"""
from __future__ import annotations

from typing import Callable

from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.dto import TenantDomainInfo, TenantSnapshot
from core.modules.tenant.ports import TenantRepositoryPort, TenantSchemaManagerPort, TenantUserProvisioningPort
from core.modules.tenant.domain.tenant_policy import TenantLifecyclePolicy
from core.modules.tenant.provisioning.models import (
    ProvisioningCompensationPlan,
    TenantProvisioningRequest,
    TenantProvisioningValidation,
)
from core.modules.tenant.provisioning.validator import TenantProvisioningValidator


class TenantProvisioningService:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        user_service: TenantUserProvisioningPort,
        schema_manager: TenantSchemaManagerPort,
        request_base_url_builder: Callable[[str], str],
        lifecycle_policy: TenantLifecyclePolicy | None = None,
        validator: TenantProvisioningValidator | None = None,
    ) -> None:
        self.tenant_repo = tenant_repository
        self.user_service = user_service
        self.schema_manager = schema_manager
        self.request_base_url_builder = request_base_url_builder
        self.lifecycle_policy = lifecycle_policy or TenantLifecyclePolicy()
        self.validator = validator or TenantProvisioningValidator(
            tenant_repository=tenant_repository,
            user_service=user_service,
            schema_manager=schema_manager,
        )

    def validate_provisioning_state(self, request: TenantProvisioningRequest) -> TenantProvisioningValidation:
        return self.validator.validate(request)

    def _ensure_schema(self, slug: str, plan: ProvisioningCompensationPlan) -> None:
        schema_present_before = self.schema_manager.exists(slug)
        self.schema_manager.create(slug)
        if not schema_present_before and self.schema_manager.exists(slug):
            plan.schema_created = True

    def _ensure_tenant(self, request: TenantProvisioningRequest, plan: ProvisioningCompensationPlan):
        tenant = self.tenant_repo.get_by_slug(request.slug)
        if tenant is not None:
            return tenant
        tenant = self.tenant_repo.create(
            request.slug,
            request.tenant_name,
            created_by=None,
            is_active=False,
        )
        plan.tenant_created = True
        return tenant

    def _ensure_owner(self, request: TenantProvisioningRequest):
        token = current_tenant_schema.set(request.slug)
        try:
            existing = self.user_service.user_repository.get_by_email(request.owner_email)
            if existing is not None:
                return existing
            base_url = self.request_base_url_builder(request.slug)
            return self.user_service.create(
                email=request.owner_email,
                name=request.owner_name,
                role="owner",
                request_base_url=base_url,
                send_invite_email=request.owner_send_invite_email,
                activate_immediately=request.owner_activate_immediately,
                invite_lang=request.owner_invite_lang,
            )
        finally:
            current_tenant_schema.reset(token)

    def _ensure_actor(self, tenant_id: int, owner_id: int, plan: ProvisioningCompensationPlan) -> None:
        previous_actor = self.tenant_repo.get_actor_user_id(tenant_id)
        if previous_actor == owner_id:
            return
        plan.previous_actor_user_id = previous_actor
        self.tenant_repo.set_actor(tenant_id, owner_id, updated_by=owner_id)
        plan.actor_changed = True

    def _ensure_config(self, request: TenantProvisioningRequest, tenant_id: int, owner_id: int, plan: ProvisioningCompensationPlan) -> None:
        existing = self.tenant_repo.get_config_by_tenant_id(tenant_id, slug=request.slug)
        if existing is None:
            plan.config_created = True
        self.tenant_repo.create_config(
            tenant_id,
            slug=request.slug,
            package=request.package,
            feature_flags=request.feature_flags or {},
            limits=request.limits or {},
            created_by=owner_id,
        )

    def _ensure_domain(
        self,
        tenant_id: int,
        domain: str | None,
        *,
        owner_id: int,
        plan: ProvisioningCompensationPlan,
    ) -> None:
        if not domain:
            return
        existing = self.tenant_repo.get_domain(domain)
        if existing is None:
            self.tenant_repo.create_domain(tenant_id, domain, created_by=owner_id)
            plan.domains_created.append(domain)
            return
        if existing.tenant_id != tenant_id:
            raise ValueError("domain_taken")

    def _ensure_activation(self, tenant_id: int, slug: str, owner_id: int) -> None:
        status = self.tenant_repo.get_tenant_status(slug)
        if status is not None and status.is_active:
            return
        self.lifecycle_policy.assert_transition(status, TenantLifecyclePolicy.ACTIVE)
        self.tenant_repo.activate(tenant_id, updated_by=owner_id)

    def _compensate(self, request: TenantProvisioningRequest, plan: ProvisioningCompensationPlan) -> None:
        for domain in reversed(plan.domains_created):
            self.tenant_repo.delete_domain(domain)
        if plan.config_created:
            tenant = self.tenant_repo.get_by_slug(request.slug)
            if tenant and tenant.id is not None:
                self.tenant_repo.delete_config(tenant.id, slug=request.slug)
        if plan.actor_changed:
            tenant = self.tenant_repo.get_by_slug(request.slug)
            if tenant and tenant.id is not None:
                self.tenant_repo.set_actor(tenant.id, plan.previous_actor_user_id, updated_by=plan.previous_actor_user_id)
        if plan.tenant_created:
            self.tenant_repo.delete_by_slug(request.slug)
        if plan.schema_created:
            self.schema_manager.drop(request.slug)

    def provision(self, request: TenantProvisioningRequest) -> TenantSnapshot:
        plan = ProvisioningCompensationPlan()
        try:
            self._ensure_schema(request.slug, plan)
            tenant = self._ensure_tenant(request, plan)
            if tenant.id is None:
                raise RuntimeError("tenant_id_missing_after_ensure")
            owner = self._ensure_owner(request)
            if owner is None or owner.id is None:
                raise RuntimeError("owner_missing_after_ensure")
            self._ensure_actor(tenant.id, owner.id, plan)
            self._ensure_config(request, tenant.id, owner.id, plan)
            self._ensure_domain(tenant.id, request.primary_domain, owner_id=owner.id, plan=plan)
            self._ensure_domain(tenant.id, request.custom_domain, owner_id=owner.id, plan=plan)
            self._ensure_activation(tenant.id, request.slug, owner.id)

            validation = self.validate_provisioning_state(request)
            if not validation.is_consistent:
                raise RuntimeError(f"tenant_provisioning_inconsistent:{validation}")

            snapshot = self.tenant_repo.get_snapshot_by_slug(request.slug)
            if snapshot is None:
                raise RuntimeError("tenant_snapshot_missing_after_provisioning")
            return snapshot.with_domain(
                TenantDomainInfo(
                    request_host=request.primary_domain,
                    resolved_host=request.primary_domain,
                    is_custom_domain=False,
                    verified_at=None,
                )
            )
        except Exception:
            # Compensate on any failure – catching broadly is intentional:
            # we must roll back partial state regardless of error type.
            self._compensate(request, plan)
            raise


__all__ = [
    "TenantProvisioningRequest",
    "TenantProvisioningService",
    "TenantProvisioningValidation",
]
