from functools import lru_cache

from core.kernel.config.loader import load_config


@lru_cache(maxsize=1)
def get_settings():
    return load_config()

def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(name)


__all__ = ["get_settings", "settings"]
