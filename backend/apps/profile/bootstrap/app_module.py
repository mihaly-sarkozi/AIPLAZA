from __future__ import annotations

# backend/apps/profile/bootstrap/app_module.py
# Feladat: A profile app modul runtime beüzemelése, service-regisztrációja, routere és tenant hookja.
# Sárközi Mihály - 2026.05.24

from apps.profile.api.router import router
from apps.profile.bootstrap.service_keys import PROFILE_SERVICE
from apps.profile.infra.preferences_repository import ProfilePreferencesRepository
from apps.profile.service.preferences_service import ProfilePreferencesService
from apps.profile.service.profile_facade import ProfileFacade
from apps.profile.bootstrap.tenant_hooks import register_profile_tenant_hooks
from core.kernel.interface import BaseAppModule, ModuleContext, RouteRegistration
from core.kernel.interface.app_conventions import module_key, module_route_tag
from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE, PLATFORM_USERS_PROFILE_SERVICE


class ProfileAppModule(BaseAppModule):
    key = module_key("profile")

    def service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_USERS_PROFILE_SERVICE,)

    def optional_service_dependencies(self) -> tuple[str, ...]:
        return (PLATFORM_TENANT_USAGE_SERVICE,)

    def register(self, container: ModuleContext) -> None:
        preferences_repository = ProfilePreferencesRepository(container.session_factory.engine)
        preferences_service = ProfilePreferencesService(preferences_repository)
        facade = ProfileFacade(
            core_profile_service=container.get_platform_service(PLATFORM_USERS_PROFILE_SERVICE),
            preferences_service=preferences_service,
            training_status_reader=container.get_optional_service(PLATFORM_TENANT_USAGE_SERVICE),
        )
        container.register_service(PROFILE_SERVICE, facade)

    def routers(self) -> tuple[RouteRegistration, ...]:
        return (RouteRegistration(router=router, prefix="/api", tags=(module_route_tag("profile"),)),)

    def tenant_schema_hooks(self) -> tuple:
        return (register_profile_tenant_hooks,)

    def permissions(self) -> tuple[str, ...]:
        return ("profile.read", "profile.write")


def get_module() -> BaseAppModule:
    return ProfileAppModule()


__all__ = ["ProfileAppModule", "get_module"]
