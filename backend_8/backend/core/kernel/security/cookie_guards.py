# backend/core/kernel/security/cookie_guards.py
# Feladat: Refresh cookie SameSite és Secure konfigurációját validálja induláskor. Megakadályozza az érvénytelen SameSite értékeket, a SameSite=None + insecure kombinációt és productionben a cookie_secure=False beállítást. Core startup security guard a böngészős token cookie policyhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.config.environment import is_deployed_env
from core.kernel.security.errors import SecurityConfigError

_VALID_SAMESITE_VALUES = {"lax", "strict", "none"}


def validate_secure_refresh_cookie_policy(settings: object, env: str) -> None:
    samesite = (getattr(settings, "cookie_samesite", "lax") or "lax").strip().lower()
    secure = bool(getattr(settings, "cookie_secure", True))

    if samesite not in _VALID_SAMESITE_VALUES:
        raise SecurityConfigError(
            f"cookie_samesite érvénytelen érték: {samesite!r}. "
            f"Megengedett értékek: {sorted(_VALID_SAMESITE_VALUES)}"
        )

    if samesite == "none" and not secure:
        raise SecurityConfigError(
            "cookie_samesite='none' csak cookie_secure=True esetén érvényes "
            "(a böngésző különben elutasítja a cookie-t)."
        )

    if is_deployed_env(env) and not secure:
        raise SecurityConfigError(
            "cookie_secure=False staging/production környezetben nem engedélyezett. "
            "Az alkalmazás csak HTTPS-en keresztül üzemeltethető deployolt környezetben."
        )


__all__ = ["validate_secure_refresh_cookie_policy"]
