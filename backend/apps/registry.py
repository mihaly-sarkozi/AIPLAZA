# backend/apps/registry.py
# Feladata: megmondja, milyen telepített app modulok léteznek és melyek aktívak.
# DISABLED_APP_MODULES alapján ki lehet kapcsolni modulokat
# Dinamikusan importálja a get_module() factorykat, és visszaadja az aktív app modulokat.
# Fontos: ez sem indítja el a modulok belső működését. Csak létrehozza a BaseAppModule objektumokat. A tényleges register() később az AppContainer / bootstrap/modules.py alatt fut.
# Sárközi Mihály - 2026.05.17

from __future__ import annotations

import os
from functools import lru_cache

from core.kernel.interface import BaseAppModule

# Az apps modulokat kell regisztrálni az APP_MODULES változóban.
APP_MODULES: tuple[tuple[str, str], ...] = (
    ("settings", "apps.settings.bootstrap.app_module:get_module"),
    ("billing", "apps.billing.bootstrap.app_module:get_module"),
    ("kb", "apps.kb.bootstrap.app_module:get_module"),
    ("chat", "apps.chat.bootstrap.app_module:get_module"),
    ("demo", "apps.demo.bootstrap.app_module:get_module"),
    ("landing", "apps.landing.bootstrap.app_module:get_module"),
    ("orders", "apps.orders.bootstrap.app_module:get_module"),
    ("packages", "apps.packages.bootstrap.app_module:get_module"),
    ("profile", "apps.profile.bootstrap.app_module:get_module"),
    ("traffic", "apps.traffic.bootstrap.app_module:get_module"),
)

# Az aktív app modulokat tölti be, amelyek nem szerepelnek a DISABLED_APP_MODULES környezeti változóban.
def load_app_modules() -> tuple[BaseAppModule, ...]:
    disabled = {
        item.strip().lower()
        for item in (os.getenv("DISABLED_APP_MODULES", "") or "").split(",")
        if item.strip()
    }
    return tuple(
        load_app_module(factory_path)
        for module_name, factory_path in APP_MODULES
        if module_name not in disabled
    )


# Dinamikus importálja az app modulok elérését.
@lru_cache(maxsize=None)
def load_app_module(factory_path: str) -> BaseAppModule:
    module_path, function_name = factory_path.rsplit(":", 1)
    module = __import__(module_path, fromlist=[function_name])
    factory = getattr(module, function_name)
    return factory()

__all__ = [
    "load_app_modules",
    "load_app_module",
]
