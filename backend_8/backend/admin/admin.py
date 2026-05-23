# backend/admin/admin.py
# Feladat: A backend-szintű platform admin komponenst regisztráló BaseAppModule implementáció. Felépíti és service kulcson publikálja a PlatformAdminService-t, beköti a /api/platform-admin routert, startupkor pedig létrehozza az első admin felhasználót, ha a bootstrap beállítások meg vannak adva. Platform-admin module assembly, amely már nem a core/modules része.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.routing import RouteRegistration
from core.kernel.interface.keys import PLATFORM_ADMIN_SERVICE
from admin.repository.platform_admin_repository import PlatformAdminRepository
from admin.router.admin_router import router as platform_admin_router
from admin.service.platform_admin_service import PlatformAdminService


class AdminCoreModule(BaseAppModule):
    key = "platform.admin"

    def register(self, container: ModuleContext) -> None:
        service = PlatformAdminService(
            repository=PlatformAdminRepository(container.session_factory),
            token_service=container.security.token_service,
            email_service=container.email_service,
        )
        container.register_service(PLATFORM_ADMIN_SERVICE, service)

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=platform_admin_router, prefix="/api", tags=("platform-admin",)),)

    def startup_hooks(self) -> tuple:
        def _bootstrap(_app) -> None:
            from core.kernel.deps.facade import get_service

            get_service(PLATFORM_ADMIN_SERVICE).bootstrap_first_admin()

        return (_bootstrap,)
