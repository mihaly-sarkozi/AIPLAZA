# backend/core/modules/auth/domain/exceptions/__init__.py
# Feladat: Az auth domain exceptionök lazy exportfelülete. A 2FA email küldési és túl sok próbálkozás hibákat adja ki anélkül, hogy importkor minden üzenetkezelési függőséget betöltene. Auth domain exception csomagbelépő.
# Sárközi Mihály - 2026.05.21

"""Auth kivételek: lazy re-export (lang.messages-t nem töltjük be előre)."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.modules.auth.domain.exceptions.two_factor_email_error import TwoFactorEmailError
    from core.modules.auth.domain.exceptions.two_factor_too_many_attempts_error import (
        TwoFactorTooManyAttemptsError,
    )

_LAZY: dict[str, tuple[str, str]] = {
    "TwoFactorEmailError": (
        "core.modules.auth.domain.exceptions.two_factor_email_error",
        "TwoFactorEmailError",
    ),
    "TwoFactorTooManyAttemptsError": (
        "core.modules.auth.domain.exceptions.two_factor_too_many_attempts_error",
        "TwoFactorTooManyAttemptsError",
    ),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib

        module_path, attr = _LAZY[name]
        mod = importlib.import_module(module_path)
        return getattr(mod, attr)
    raise AttributeError(name)


__all__ = [
    "TwoFactorEmailError",
    "TwoFactorTooManyAttemptsError",
]
