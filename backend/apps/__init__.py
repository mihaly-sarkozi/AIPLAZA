# Ez a fájl a(z) apps csomag exportjait és inicializálási pontjait fogja össze.
from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache

from core.platform.contract import AppModule


@lru_cache(maxsize=None)
def _load_module(factory_path: str) -> AppModule:
    """Load each app module once per process.

    The platform builds the app manifest more than once during startup
    (routing/lifecycle assembly and runtime container bootstrap). App modules
    therefore must be stable by identity, otherwise a startup hook may execute
    on a different AppModule instance than the one that received `register()`.
    """
    module_path, function_name = factory_path.rsplit(":", 1)
    module = __import__(module_path, fromlist=[function_name])
    factory = getattr(module, function_name)
    return factory()


def get_chat_module():
    return _load_module("apps.chat.module:get_module")


def get_billing_module():
    return _load_module("apps.billing.module:get_module")


def get_knowledge_module():
    return _load_module("apps.knowledge.module:get_module")


def get_settings_module():
    return _load_module("apps.settings.module:get_module")


def get_demo_module():
    return _load_module("apps.demo.module:get_module")


def get_landing_module():
    return _load_module("apps.landing.module:get_module")


def get_orders_module():
    return _load_module("apps.orders.module:get_module")


def get_packages_module():
    return _load_module("apps.packages.module:get_module")


def get_profile_module():
    return _load_module("apps.profile.module:get_module")


def get_traffic_module():
    return _load_module("apps.traffic.module:get_module")


APP_MODULE_LOADERS: tuple[tuple[str, Callable[[], AppModule]], ...] = (
    ("settings", get_settings_module),
    ("billing", get_billing_module),
    ("knowledge", get_knowledge_module),
    ("chat", get_chat_module),
    ("demo", get_demo_module),
    ("landing", get_landing_module),
    ("orders", get_orders_module),
    ("packages", get_packages_module),
    ("profile", get_profile_module),
    ("traffic", get_traffic_module),
)


def load_enabled_app_modules() -> tuple:
    """Return the tuple of enabled AppModule instances based on DISABLED_APP_MODULES env var.

    This is the composition-root loader: it is passed to
    ``core.platform.bootstrap.manifest.configure_app_modules_loader`` in
    ``main.py``.  The platform layer never calls this function directly.
    """
    disabled = {
        item.strip().lower()
        for item in (os.getenv("DISABLED_APP_MODULES", "") or "").split(",")
        if item.strip()
    }
    modules = [
        loader()
        for module_name, loader in APP_MODULE_LOADERS
        if module_name not in disabled
    ]
    return tuple(modules)


__all__ = [
    "get_billing_module",
    "get_chat_module",
    "get_demo_module",
    "get_knowledge_module",
    "get_landing_module",
    "get_orders_module",
    "get_packages_module",
    "get_profile_module",
    "get_settings_module",
    "get_traffic_module",
    "load_enabled_app_modules",
]
