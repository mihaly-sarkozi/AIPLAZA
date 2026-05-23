# backend/core/modules/users/router/responses/__init__.py
# Feladat: A users router response DTO-k lazy exportfelülete. UserResponse modelt ad tovább auth, admin és invite routerek számára. Users web response contract belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["UserResponse"]


def __getattr__(name: str):
    if name == "UserResponse":
        return getattr(importlib.import_module("core.modules.users.router.responses.user_response"), "UserResponse")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
