# backend/core/kernel/domain/module.py
# Feladat: A kernel domain routing komponenst regisztráló BaseAppModule implementáció. Felépíti a DomainRepository, DomainRoutingPolicy, DomainPolicy, TenantDomainVerificationService és DomainService komponenseket, platform service kulcsokon publikálja őket, és beköti a domain routert. Core kernel domain assembly, amely a tenant lifecycle policyre épül.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.config.config_loader import settings
from core.kernel.interface.routing import RouteRegistration
from core.kernel.domain.policies import DomainPolicy
from core.kernel.domain.repositories import DomainRepository
from core.kernel.domain.router import router as domain_router
from core.kernel.domain.services import DomainService
from core.modules.tenant.service import TenantDomainVerificationService
from core.modules.tenant.domain.tenant_policy import DomainRoutingPolicy
from core.kernel.interface.keys import (
    PLATFORM_DOMAIN_POLICY,
    PLATFORM_DOMAIN_REPOSITORY,
    PLATFORM_DOMAIN_ROUTING_POLICY,
    PLATFORM_DOMAIN_SERVICE,
    PLATFORM_DOMAIN_VERIFICATION_SERVICE,
    PLATFORM_TENANT_LIFECYCLE_POLICY,
)


class DomainCoreModule(BaseAppModule):
    key = "platform.domain"

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_TENANT_LIFECYCLE_POLICY,)

    def register(self, container: ModuleContext) -> None:
        repo = DomainRepository(container.infrastructure.repositories.tenant_repo)
        verification_service = TenantDomainVerificationService(container.infrastructure.repositories.tenant_repo)
        lifecycle_policy = container.get_service(PLATFORM_TENANT_LIFECYCLE_POLICY)
        routing_policy = DomainRoutingPolicy(
            tenant_base_domain=settings.tenant_base_domain,
            localhost_tenant=settings.single_tenant_slug,
        )
        policy = DomainPolicy(
            tenant_base_domain=settings.tenant_base_domain,
            lifecycle_policy=lifecycle_policy,
            routing_policy=routing_policy,
        )
        service = DomainService(repo, policy, verification_service)
        container.register_repository(PLATFORM_DOMAIN_REPOSITORY, repo)
        container.register_service(PLATFORM_DOMAIN_ROUTING_POLICY, routing_policy)
        container.register_service(PLATFORM_DOMAIN_POLICY, policy)
        container.register_service(PLATFORM_DOMAIN_VERIFICATION_SERVICE, verification_service)
        container.register_service(PLATFORM_DOMAIN_SERVICE, service)

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=domain_router, prefix="/api", tags=("platform-domain",)),)

    def permissions(self) -> tuple[str, ...]:
        return ("domain.read", "domain.write")
