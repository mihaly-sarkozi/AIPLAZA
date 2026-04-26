from __future__ import annotations

from apps.contracts import module_key, module_route_tag
from apps.settings.api.router import router as settings_router
from apps.settings.contracts import SETTINGS_SERVICE
from apps.settings.service.settings_facade import SettingsFacade
from core.platform.contract import AppModule, ModuleContext, RouteRegistration
from core.platform.service_keys import PLATFORM_SETTINGS_SERVICE
from core.platform.settings.sections import list_settings_sections


class SettingsAppModule(AppModule):
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


def get_module() -> AppModule:
    return SettingsAppModule()
