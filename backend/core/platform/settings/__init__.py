from __future__ import annotations

__all__ = [
    "SettingsSection",
    "list_settings_sections",
    "register_settings_section",
    "register_settings_tenant_hooks",
]


def __getattr__(name: str):
    import importlib

    _map = {
        "SettingsSection": ("core.platform.settings.sections", "SettingsSection"),
        "list_settings_sections": ("core.platform.settings.sections", "list_settings_sections"),
        "register_settings_section": ("core.platform.settings.sections", "register_settings_section"),
        "register_settings_tenant_hooks": ("core.platform.settings.tenant_hooks", "register_settings_tenant_hooks"),
    }
    if name in _map:
        module_path, attr = _map[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(f"module 'core.platform.settings' has no attribute {name!r}")
