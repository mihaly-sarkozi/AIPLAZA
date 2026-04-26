# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from core.platform.composition import AppModule, ModuleContext
from core.kernel.config.config_loader import settings
from core.platform.contract.routing import RouteRegistration
from core.platform.domain.policies import DomainPolicy
from core.platform.domain.repositories import DomainRepository
from core.platform.domain.router import router as domain_router
from core.platform.domain.services import DomainService
from core.extensions.tenant.service import TenantDomainVerificationService
from core.platform.tenant_policy import DomainRoutingPolicy, TenantLifecyclePolicy
from core.platform.service_keys import (
    PLATFORM_DOMAIN_POLICY,
    PLATFORM_DOMAIN_REPOSITORY,
    PLATFORM_DOMAIN_ROUTING_POLICY,
    PLATFORM_DOMAIN_SERVICE,
    PLATFORM_DOMAIN_VERIFICATION_SERVICE,
    PLATFORM_TENANT_LIFECYCLE_POLICY,
)


class DomainPlatformModule(AppModule):
    key = "platform.domain"

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_TENANT_LIFECYCLE_POLICY,)

    # Ez a metódus regisztrálja a(z) register logikáját.
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

    # Ez a metódus a(z) routers logikáját valósítja meg.
    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=domain_router, prefix="/api", tags=("platform-domain",)),)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return ("domain.read", "domain.write")


# Ez a függvény visszaadja a(z) modul logikáját.
def get_module() -> AppModule:
    return DomainPlatformModule()
