from __future__ import annotations

import importlib

__all__ = ["check_login_step1_email", "check_login_step2_pending_token"]

_LAZY: dict[str, tuple[str, str]] = {
    "check_login_step1_email": (
        "core.capabilities.auth.rate_limit.auth_limits",
        "check_login_step1_email",
    ),
    "check_login_step2_pending_token": (
        "core.capabilities.auth.rate_limit.auth_limits",
        "check_login_step2_pending_token",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
