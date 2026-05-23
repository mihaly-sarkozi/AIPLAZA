# backend/core/modules/auth/web/rate_limit/__init__.py
# Feladat: Az auth login rate limit helperök lazy exportfelülete. Step1 email és step2 pending token limit ellenőrzéseket ad ki, miközben a Redis/in-memory adapter importját késlelteti. Auth web rate limit csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import importlib

__all__ = ["check_login_step1_email", "check_login_step2_pending_token"]

_LAZY: dict[str, tuple[str, str]] = {
    "check_login_step1_email": (
        "core.modules.auth.web.rate_limit.auth_limits",
        "check_login_step1_email",
    ),
    "check_login_step2_pending_token": (
        "core.modules.auth.web.rate_limit.auth_limits",
        "check_login_step2_pending_token",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
