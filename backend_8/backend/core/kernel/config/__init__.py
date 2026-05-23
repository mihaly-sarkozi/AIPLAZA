# backend/core/kernel/config/__init__.py
# Feladat: A config csomag rövid, publikus importfelületét adja. Lazy proxyként teszi elérhetővé a `settings` objektumot, hogy a csomag importja önmagában ne kényszerítsen teljes settings betöltést minden helyzetben. A core és app modulok stabil belépési pontként használhatják, de a konkrét betöltési logika a config_loader.py-ban van.
# Sárközi Mihály - 2026.05.22

def __getattr__(name: str):
    if name == "settings":
        from core.kernel.config.config_loader import settings

        return settings
    raise AttributeError(name)

__all__ = ["settings"]
