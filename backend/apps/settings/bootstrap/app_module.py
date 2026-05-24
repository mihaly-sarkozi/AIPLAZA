from __future__ import annotations

# backend/apps/settings/bootstrap/module.py
# Feladat: A settings app modul runtime beüzemelése. Regisztrálja a settings szolgáltatást, route-ot, permissionöket és core settings service függőséget.
# Sárközi Mihály - 2026.05.24

from apps.settings.api.router import router as settings_router
from apps.settings.bootstrap.service_keys import SETTINGS_SERVICE
from apps.settings.service.settings_facade import SettingsFacade
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key, module_route_tag
from core.kernel.interface.keys import PLATFORM_SETTINGS_SERVICE
from core.modules.settings.registry.settings_section_registry import list_settings_sections


class SettingsAppModule(BaseAppModule):
    key = module_key("settings")

    def register(self, container: ModuleContext) -> None:
        container.register_service(
            SETTINGS_SERVICE,
            SettingsFacade(
                core_settings_service=container.get_platform_service(PLATFORM_SETTINGS_SERVICE),
                sections_lister=list_settings_sections,
            ),
        )

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=settings_router, prefix="/api", tags=(module_route_tag("settings"),)),)

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_SETTINGS_SERVICE,)

    def permissions(self) -> tuple[str, ...]:
        return ("settings.read", "settings.write")


def get_module() -> BaseAppModule:
    return SettingsAppModule()


__all__ = ["SettingsAppModule", "get_module"]
