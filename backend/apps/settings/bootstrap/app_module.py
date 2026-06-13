from __future__ import annotations

# backend/apps/settings/bootstrap/module.py
# Feladat: A settings app modul runtime beüzemelése. Regisztrálja a settings szolgáltatást, route-ot, permissionöket és core settings service függőséget.
# Sárközi Mihály - 2026.05.24

import os

from apps.settings.api.router import router as settings_router
from apps.settings.bootstrap.service_keys import SETTINGS_SERVICE, TENANT_RESET_SERVICE
from apps.settings.service.settings_facade import SettingsFacade
from apps.settings.service.tenant_reset_service import TenantResetService
from core.kernel.config.environment import normalize_app_env
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key, module_route_tag
from core.kernel.interface.keys import PLATFORM_SETTINGS_SERVICE
from core.modules.settings.registry.settings_section_registry import list_settings_sections


def _require_eu_vat_validation() -> bool:
    explicit = (os.getenv("SETTINGS_REQUIRE_EU_VAT_VALIDATION") or "").strip().lower()
    if explicit:
        return explicit in {"1", "true", "yes", "on"}
    return normalize_app_env(os.getenv("APP_ENV", "local")) == "production"


class SettingsAppModule(BaseAppModule):
    key = module_key("settings")

    def register(self, container: ModuleContext) -> None:
        container.register_service(
            SETTINGS_SERVICE,
            SettingsFacade(
                core_settings_service=container.get_platform_service(PLATFORM_SETTINGS_SERVICE),
                sections_lister=list_settings_sections,
                require_eu_vat_validation=_require_eu_vat_validation(),
            ),
        )
        container.register_service(
            TENANT_RESET_SERVICE,
            TenantResetService(session_factory=container.session_factory),
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
