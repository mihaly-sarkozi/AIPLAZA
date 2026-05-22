# backend/core/kernel/security/rate_limit_guards.py
# Feladat: Rate limit konfiguráció és production Redis jelenlét induláskori validációja. Ellenőrzi, hogy a login limit pozitív és productionben nem túl magas, valamint éles környezetben Redis URL legyen megadva több példányos rate limithez és token allowlisthoz. Core startup security guard a throttling infrastruktúrához.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.config.environment import is_deployed_env, is_production_env
from core.kernel.security.errors import SecurityConfigError

_MAX_REASONABLE_RATE_LIMIT = 200


def validate_rate_limit_config(settings: object, env: str) -> None:
    raw = getattr(settings, "rate_limit_login_per_minute", None)
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        raise SecurityConfigError(
            f"rate_limit_login_per_minute érvénytelen érték: {raw!r}. "
            "Pozitív egész számnak kell lennie."
        )

    if limit <= 0:
        raise SecurityConfigError(
            f"rate_limit_login_per_minute értéke {limit}, de pozitívnak kell lennie."
        )

    if limit > _MAX_REASONABLE_RATE_LIMIT:
        raise SecurityConfigError(
            f"rate_limit_login_per_minute={limit} értéke indokolatlanul magas "
            f"(ajánlott maximum: {_MAX_REASONABLE_RATE_LIMIT}/perc)."
        )

    if is_production_env(env) and limit > 30:
        raise SecurityConfigError(
            f"rate_limit_login_per_minute={limit} production-ben túl magas "
            "(ajánlott maximum login végponton: 30/perc). "
            "Brute-force védelem érdekében csökkentsd le."
        )


def validate_production_redis_url(settings: object, env: str) -> None:
    if not is_deployed_env(env):
        return
    url = (getattr(settings, "redis_url", "") or "").strip()
    if not url:
        raise SecurityConfigError(
            "redis_url staging/production környezetben kötelező: a globális rate limiter, replay védelem "
            "és token allowlist megosztott tárolót igényel (in-memory fallback nem engedélyezett)."
        )


__all__ = ["validate_production_redis_url", "validate_rate_limit_config"]
