# backend/core/modules/auth/router/responses/__init__.py
# Feladat: Az auth router response modellek lazy exportfelülete. TokenResponse és TwoFactorRequiredResponse modelleket ad ki anélkül, hogy importkor minden válaszséma betöltődne. Auth HTTP response schema csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["TokenResponse", "TwoFactorRequiredResponse"]

_LAZY: dict[str, tuple[str, str]] = {
    "TokenResponse": (
        "core.modules.auth.router.responses.token_response",
        "TokenResponse",
    ),
    "TwoFactorRequiredResponse": (
        "core.modules.auth.router.responses.two_factor_required_response",
        "TwoFactorRequiredResponse",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
