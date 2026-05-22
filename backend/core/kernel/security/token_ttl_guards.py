# backend/core/kernel/security/token_ttl_guards.py
# Feladat: Access és refresh token TTL konfigurációt validál induláskor. Biztosítja, hogy az értékek pozitívak, az access token rövidebb életű legyen a refresh tokennél, és productionben ne legyen indokolatlanul hosszú TTL. Core startup security guard a token élettartam policyhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.config.environment import is_production_env
from core.kernel.security.errors import SecurityConfigError

_MAX_PROD_ACCESS_TTL_MIN = 60
_MAX_PROD_REFRESH_TTL_DAYS = 90


def validate_refresh_token_policy(settings: object, env: str) -> None:
    try:
        access_ttl = int(getattr(settings, "access_ttl_min", 15))
        refresh_days = int(getattr(settings, "refresh_ttl_days", 30))
        refresh_session_hours = int(getattr(settings, "refresh_ttl_session_hours", 24))
    except (TypeError, ValueError) as exc:
        raise SecurityConfigError(f"Érvénytelen TTL konfiguráció: {exc}") from exc

    if access_ttl <= 0:
        raise SecurityConfigError(
            f"access_ttl_min értéke {access_ttl}, de pozitívnak kell lennie."
        )
    if refresh_days <= 0:
        raise SecurityConfigError(
            f"refresh_ttl_days értéke {refresh_days}, de pozitívnak kell lennie."
        )
    if refresh_session_hours <= 0:
        raise SecurityConfigError(
            f"refresh_ttl_session_hours értéke {refresh_session_hours}, de pozitívnak kell lennie."
        )

    refresh_days_in_min = refresh_days * 24 * 60
    if access_ttl >= refresh_days_in_min:
        raise SecurityConfigError(
            f"access_ttl_min ({access_ttl} perc) nem lehet >= refresh_ttl_days "
            f"({refresh_days} nap = {refresh_days_in_min} perc). "
            "Az access token élettartama rövidebb kell legyen a refresh tokenénél."
        )

    if is_production_env(env):
        if access_ttl > _MAX_PROD_ACCESS_TTL_MIN:
            raise SecurityConfigError(
                f"access_ttl_min={access_ttl} perc production-ben túl hosszú "
                f"(ajánlott maximum: {_MAX_PROD_ACCESS_TTL_MIN} perc)."
            )
        if refresh_days > _MAX_PROD_REFRESH_TTL_DAYS:
            raise SecurityConfigError(
                f"refresh_ttl_days={refresh_days} production-ben indokolatlanul hosszú "
                f"(ajánlott maximum: {_MAX_PROD_REFRESH_TTL_DAYS} nap)."
            )


__all__ = ["validate_refresh_token_policy"]
