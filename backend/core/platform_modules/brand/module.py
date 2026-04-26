# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from core.platform.composition import AppModule, ModuleContext
from core.platform.contract.routing import RouteRegistration
from core.platform.brand.repositories import BrandRepository
from core.platform.brand.router import router as brand_router
from core.platform.brand.services import BrandService
from core.platform.brand.tenant_hooks import register_brand_tenant_hooks
from core.platform.service_keys import PLATFORM_BRAND_REPOSITORY, PLATFORM_BRAND_SERVICE


class BrandPlatformModule(AppModule):
    key = "platform.brand"

    # Ez a metódus regisztrálja a(z) register logikáját.
    def register(self, container: ModuleContext) -> None:
        repo = BrandRepository(container.infrastructure.db_session_factory)
        service = BrandService(repo, audit_service=container.audit_service)
        container.register_repository(PLATFORM_BRAND_REPOSITORY, repo)
        container.register_service(PLATFORM_BRAND_SERVICE, service)

    # Ez a metódus a(z) routers logikáját valósítja meg.
    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=brand_router, prefix="/api", tags=("platform-brand",)),)

    # Ez a metódus a(z) tenant_schema_hooks logikáját valósítja meg.
    def tenant_schema_hooks(self) -> tuple:
        return (register_brand_tenant_hooks,)

    # Ez a metódus a(z) permissions logikáját valósítja meg.
    def permissions(self) -> tuple[str, ...]:
        return ("brand.read", "brand.write")


# Ez a függvény visszaadja a(z) modul logikáját.
def get_module() -> AppModule:
    return BrandPlatformModule()
