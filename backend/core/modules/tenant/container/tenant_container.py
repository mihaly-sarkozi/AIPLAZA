# backend/core/modules/tenant/container/tenant_container.py
# Feladat: A tenant modul belső dependency assembly objektuma. Repositorykat, schema managert, provisioning/sign-up orchestratorokat, token service-t és lifecycle policyt köt össze az infrastruktúra adapterekkel. Tenant composition réteg a TenantCoreModule alatt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from dataclasses import dataclass

from core.modules.tenant.repositories import TenantRepository
from core.modules.tenant.repositories.demo_signup_repository import DemoSignupRepository
from core.modules.tenant.schema.manager import SqlAlchemyTenantSchemaManager
from core.modules.tenant.signup.orchestrator import TenantSignupOrchestrator
from core.modules.tenant.signup.service import TenantSignupService
from core.modules.tenant.provisioning.provisioner import TenantProvisioningService
from core.modules.tenant.tokens.demo_jwt import DemoLoginTokenService
from core.modules.users.service.user_service import UserService
from core.infrastructure.audit.service.audit_service import AuditService
from core.kernel.config.config_loader import settings
from core.modules.tenant.extensions.tenant_hooks import TenantExtensionRegistry, get_tenant_extension_registry
from core.modules.tenant.domain.tenant_policy import TenantLifecyclePolicy
from core.kernel.runtime.clock import Clock


@dataclass(frozen=True)
class TenantExtensionContainer:
    tenant_repo: TenantRepository
    user_service: UserService
    db_engine: object
    lifecycle_policy: TenantLifecyclePolicy
    clock: Clock
    token_service: object
    audit_service: AuditService | None = None
    tenant_extension_registry: TenantExtensionRegistry | None = None

    def build_tenant_signup_service(self, request_base_url_builder) -> TenantSignupService:
        schema_manager = SqlAlchemyTenantSchemaManager(self.db_engine)
        provisioning = TenantProvisioningService(
            tenant_repository=self.tenant_repo,
            user_service=self.user_service,
            schema_manager=schema_manager,
            request_base_url_builder=request_base_url_builder,
            lifecycle_policy=self.lifecycle_policy,
        )
        demo_signup_repository = DemoSignupRepository(self.db_engine)
        demo_token_service = DemoLoginTokenService(
            token_service=self.token_service,
            request_base_url_builder=request_base_url_builder,
            frontend_base_url=getattr(settings, "frontend_base_url", "") or "",
            cookie_secure=bool(getattr(settings, "cookie_secure", False)),
            install_host=getattr(settings, "install_host", ""),
            frontend_set_password_port=getattr(settings, "frontend_set_password_port", None),
        )
        hooks_provider = (self.tenant_extension_registry or get_tenant_extension_registry()).get_tenant_signup_hooks
        orchestrator = TenantSignupOrchestrator(
            tenant_repository=self.tenant_repo,
            user_service=self.user_service,
            provisioning_service=provisioning,
            demo_signup_repository=demo_signup_repository,
            demo_login_token_service=demo_token_service,
            tenant_base_domain=settings.tenant_base_domain,
            clock=self.clock,
            tenant_signup_hooks_provider=hooks_provider,
            audit_service=self.audit_service,
        )
        return TenantSignupService(orchestrator)


def build_tenant_extension(
    *,
    tenant_repo: TenantRepository,
    user_service: UserService,
    db_engine: object,
    lifecycle_policy: TenantLifecyclePolicy,
    clock: Clock,
    token_service: object,
    audit_service: AuditService | None = None,
    tenant_extension_registry: TenantExtensionRegistry | None = None,
) -> TenantExtensionContainer:
    return TenantExtensionContainer(
        tenant_repo=tenant_repo,
        user_service=user_service,
        db_engine=db_engine,
        lifecycle_policy=lifecycle_policy,
        clock=clock,
        token_service=token_service,
        audit_service=audit_service,
        tenant_extension_registry=tenant_extension_registry,
    )
