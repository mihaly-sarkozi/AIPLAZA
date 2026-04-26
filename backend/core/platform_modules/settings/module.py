from __future__ import annotations

from core.platform.composition import AppModule, ModuleContext
from core.platform.service_keys import PLATFORM_SETTINGS_REPOSITORY, PLATFORM_SETTINGS_SERVICE
from core.platform.settings.sections import SettingsSection, register_settings_section


class SettingsPlatformModule(AppModule):
    """Platform-level settings module.

    Registers PLATFORM_SETTINGS_SERVICE so that other platform modules (e.g.
    auth) can depend on it without any application-layer dependency. The
    application layer can add API endpoints and permissions on top of this
    platform foundation.
    """

    key = "platform.settings"

    def register(self, container: ModuleContext) -> None:
        from core.platform.settings.repositories import SettingsRepository
        from core.platform.settings.services import SettingsService

        repo = SettingsRepository(container.infrastructure.db_session_factory)
        service = SettingsService(repo, audit_service=container.audit_service)
        container.register_repository(PLATFORM_SETTINGS_REPOSITORY, repo)
        container.register_service(PLATFORM_SETTINGS_SERVICE, service)
        register_settings_section(
            SettingsSection(
                key="core.system",
                label="Core rendszer",
                path="/admin/settings?section=core.system",
                permission="settings.read",
                order=10,
                description="Felhasználók, hitelesítés és rendszerbeállítások.",
                source="core",
            )
        )

    def tenant_schema_hooks(self) -> tuple:
        from core.platform.settings.tenant_hooks import register_settings_tenant_hooks

        return (register_settings_tenant_hooks,)

    def permissions(self) -> tuple[str, ...]:
        return ()


def get_module() -> AppModule:
    return SettingsPlatformModule()
