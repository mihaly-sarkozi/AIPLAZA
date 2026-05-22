# backend/core/modules/users/domain/dto/__init__.py
# Feladat: A users DTO csomag lazy exportfelülete. A User és InviteToken adatmodelleket adja tovább auth, app modulok, repositoryk és routerek számára. Stabil users domain adatcontract belépési pont.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["InviteToken", "User"]

_LAZY: dict[str, tuple[str, str]] = {
    "InviteToken": ("core.modules.users.domain.dto.invite_token", "InviteToken"),
    "User": ("core.modules.users.domain.dto.user", "User"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
