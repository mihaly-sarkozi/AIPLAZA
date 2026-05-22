# backend/core/modules/settings/registry/__init__.py
# Feladat: A settings section registry exportfelülete. A SettingsSection típust, contributor Protocolt, registry osztályt és globális register/list/clear helper függvényeket adja tovább app és core modulok számára. Settings UI navigációs integrációs csomag belépési pont.
# Sárközi Mihály - 2026.05.21
from core.modules.settings.registry.settings_section_registry import (
    SettingsSection,
    SettingsSectionContributor,
    SettingsSectionRegistry,
    clear_settings_sections,
    list_settings_sections,
    register_settings_section,
)

__all__ = [
    "SettingsSection",
    "SettingsSectionContributor",
    "SettingsSectionRegistry",
    "clear_settings_sections",
    "list_settings_sections",
    "register_settings_section",
]
