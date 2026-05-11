from __future__ import annotations

from core.platform.composition import AppModule, ModuleContext
from core.platform.manifest import RouteRegistration
from core.platform.service_keys import PLATFORM_ADMIN_SERVICE
from core.platform_admin.repository import PlatformAdminRepository
from core.platform_admin.router import router as platform_admin_router
from core.platform_admin.service import PlatformAdminService


class PlatformAdminModule(AppModule):
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
            from core.di import get_service

            get_service(PLATFORM_ADMIN_SERVICE).bootstrap_first_admin()

        return (_bootstrap,)


def get_module() -> AppModule:
    return PlatformAdminModule()

