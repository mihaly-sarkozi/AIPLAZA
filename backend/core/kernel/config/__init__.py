# core.kernel.config - alkalmazas- es futasi konfiguracio

def __getattr__(name: str):
    if name == "settings":
        from core.kernel.config.config_loader import get_settings

        return get_settings()
    if name == "app_settings":
        from core.kernel.config.app_config_loader import get_app_settings

        return get_app_settings()
    raise AttributeError(name)

__all__ = ["settings", "app_settings"]
