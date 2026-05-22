# backend/core/modules/tenant/provisioning/validator.py
# Feladat: Tenant provisioning validációs use case. Slug, schema, repository állapot és user provisioning feltételek alapján ellenőrzi, hogy létrehozható-e az új tenant. Provisioning domain/service validációs réteg.
# Sárközi Mihály - 2026.05.21

"""Post-provisioning consistency validator.

Responsibility: check that all expected tenant artefacts (schema, tenant row,
owner user, config, domains) actually exist after provisioning.  Pure query
logic – no mutations.
"""
from __future__ import annotations

from core.modules.tenant.context.tenant_context import current_tenant_schema
from core.modules.tenant.ports import TenantRepositoryPort, TenantSchemaManagerPort, TenantUserProvisioningPort
from core.modules.tenant.provisioning.models import (
    TenantProvisioningRequest,
    TenantProvisioningValidation,
)


class TenantProvisioningValidator:
    def __init__(
        self,
        *,
        tenant_repository: TenantRepositoryPort,
        user_service: TenantUserProvisioningPort,
        schema_manager: TenantSchemaManagerPort,
    ) -> None:
        self._tenant_repository = tenant_repository
        self._user_service = user_service
        self._schema_manager = schema_manager

    def validate(self, request: TenantProvisioningRequest) -> TenantProvisioningValidation:
        tenant = self._tenant_repository.get_by_slug(request.slug)
        owner_exists = False
        if tenant is not None:
            token = current_tenant_schema.set(request.slug)
            try:
                owner = self._user_service.user_repository.get_by_email(request.owner_email)
                owner_exists = bool(owner and owner.role == "owner")
            finally:
                current_tenant_schema.reset(token)
            config = self._tenant_repository.get_config_by_tenant_id(tenant.id, slug=request.slug) if tenant.id is not None else None
        else:
            config = None
        primary_domain = self._tenant_repository.get_domain(request.primary_domain)
        custom_domain = self._tenant_repository.get_domain(request.custom_domain) if request.custom_domain else None
        schema_exists = self._schema_manager.exists(request.slug)
        missing_schema_tables = self._schema_manager.list_missing_tables(request.slug) if schema_exists else ()
        return TenantProvisioningValidation(
            tenant_exists=tenant is not None,
            owner_exists=owner_exists,
            config_exists=config is not None,
            primary_domain_exists=bool(primary_domain and tenant and primary_domain.tenant_id == tenant.id),
            custom_domain_exists=(
                True if request.custom_domain is None else bool(custom_domain and tenant and custom_domain.tenant_id == tenant.id)
            ),
            schema_exists=schema_exists,
            missing_schema_tables=missing_schema_tables,
        )


__all__ = ["TenantProvisioningValidator"]
