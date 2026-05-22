# backend/core/modules/users/domain/policies/__init__.py
# Feladat: A users policy csomag lazy exportfelülete. Profil locale/theme és login security policy helper osztályokat ad tovább service-ek és routerek számára. Users domain policy belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = [
    "build_profile_payload",
    "build_profile_updates",
    "default_owner_settings",
    "effective_locale_theme",
    "normalize_locale",
    "normalize_theme",
    "tenant_demo_mode_enabled",
]

_LAZY: dict[str, tuple[str, str]] = {
    name: ("core.modules.users.domain.policies.profile_policy", name)
    for name in __all__
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
