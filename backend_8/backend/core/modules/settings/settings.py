# backend/core/modules/settings/settings.py
# Feladat: A settings platform modult regisztráló BaseAppModule implementáció. Létrehozza a SettingsRepository és SettingsService példányokat, publikálja őket PLATFORM_SETTINGS_* kulcsokon, regisztrálja a core settings sectiont és beköti a tenant schema hookokat. Core platform module assembly a perzisztált tenant beállításokhoz.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from core.modules.settings.registry.settings_section_registry import SettingsSection, register_settings_section
from core.modules.settings.repository.settings_repository import SettingsRepository
from core.modules.settings.service.settings_service import SettingsService
from core.modules.settings.tenant_hooks import register_settings_tenant_hooks
from core.kernel.interface.base_app_module import BaseAppModule
from core.kernel.interface.module_context import ModuleContext
from core.kernel.interface.keys import PLATFORM_SETTINGS_REPOSITORY, PLATFORM_SETTINGS_SERVICE


class SettingsCoreModule(BaseAppModule):
    """Core-level settings module.

    Registers PLATFORM_SETTINGS_SERVICE so that other platform modules (e.g.
    auth) can depend on it without any application-layer dependency. The
    application layer can add API endpoints and permissions on top of this
    platform foundation.
    """

    key = "platform.settings"

    def register(self, container: ModuleContext) -> None:
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
        return (register_settings_tenant_hooks,)

    def permissions(self) -> tuple[str, ...]:
        return ()

