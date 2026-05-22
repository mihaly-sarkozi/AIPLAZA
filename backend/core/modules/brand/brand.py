# backend/core/modules/brand/brand.py
# Feladat: A platform brand modult regisztráló BaseAppModule implementáció. Felépíti a BrandRepository és BrandService példányokat, platform service kulcsokon publikálja őket, beköti a brand routert, tenant schema hookot és brand permissionöket deklarál. Core module assembly, nem HTTP vagy perzisztencia részlet.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.brand.repository.brand_repository import BrandRepository
from core.modules.brand.router.brand_router import router as brand_router
from core.modules.brand.service.brand_service import BrandService
from core.modules.brand.tenant_hooks import register_brand_tenant_hooks
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.routing import RouteRegistration
from core.kernel.interface.keys import PLATFORM_BRAND_REPOSITORY, PLATFORM_BRAND_SERVICE


class BrandCoreModule(BaseAppModule):
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

