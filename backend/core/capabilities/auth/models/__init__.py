from __future__ import annotations

import importlib

__all__ = ["AuthBase", "Pending2FAORM", "SessionORM", "TwoFactorAttemptORM", "TwoFactorCodeORM"]

_LAZY: dict[str, tuple[str, str]] = {
    "AuthBase": ("core.kernel.db.model_bases", "AuthBase"),
    "Pending2FAORM": ("core.capabilities.auth.models.pending_2fa_orm", "Pending2FAORM"),
    "SessionORM": ("core.capabilities.auth.models.session_orm", "SessionORM"),
    "TwoFactorAttemptORM": ("core.capabilities.auth.models.two_factor_attempt_orm", "TwoFactorAttemptORM"),
    "TwoFactorCodeORM": ("core.capabilities.auth.models.two_factor_code_orm", "TwoFactorCodeORM"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
