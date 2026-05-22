# backend/core/modules/auth/models/__init__.py
# Feladat: Auth perzisztencia ORM modellek exportfelulete. Ez a csomag
# tartalmazhat SQLAlchemy modelleket; a domain csomag tiszta marad.

from __future__ import annotations

from importlib import import_module
from typing import Any

_LAZY: dict[str, tuple[str, str]] = {
    "Pending2FAORM": ("core.modules.auth.models.pending_2fa_orm", "Pending2FAORM"),
    "SessionORM": ("core.modules.auth.models.session_orm", "SessionORM"),
    "TwoFactorAttemptORM": ("core.modules.auth.models.two_factor_attempt_orm", "TwoFactorAttemptORM"),
    "TwoFactorCodeORM": ("core.modules.auth.models.two_factor_code_orm", "TwoFactorCodeORM"),
    "UserAuthenticatorORM": ("core.modules.auth.models.user_authenticator_orm", "UserAuthenticatorORM"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


__all__ = list(_LAZY)
