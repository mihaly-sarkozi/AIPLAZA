# backend/core/modules/auth/router/requests/__init__.py
# Feladat: Az auth router request modellek lazy exportfelülete. A LoginRequest modellt csak kérésre importálja, hogy a router request sémák explicit és olcsó importtal maradjanak elérhetők. Auth HTTP request schema csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["LoginRequest"]


def __getattr__(name: str):
    if name == "LoginRequest":
        return getattr(
            importlib.import_module("core.modules.auth.router.requests.login_request"),
            "LoginRequest",
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
