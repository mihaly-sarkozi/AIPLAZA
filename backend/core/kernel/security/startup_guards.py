"""Kernel-szintű biztonsági indítási védelmek.

Felelősség: technikai / infrastruktúra szintű konfiguráció ellenőrzése,
mielőtt az alkalmazás elkezdi kiszolgálni a kéréseket.

Ez a modul kizárólag kernel/edge szintű ellenőrzéseket végez:
  - JWT secret erősség és entrópia
  - Cookie biztonsági flagek (Secure, SameSite)
  - CSRF védelem állapota (env var)
  - Trusted host enforcelment
  - Rate limit konfiguráció és prod-ban megosztott limiter tároló (Redis)
  - Refresh token TTL konzisztencia

Domain/policy jellegű validációk (issuer/audience, 2FA policy, jelszó policy)
a core/platform/auth/security_policy.py fájlban találhatók.

Bármilyen hiba esetén SecurityConfigError-t dob egyértelmű, cselekvésorientált
üzenettel.
"""
from __future__ import annotations

import os


class SecurityConfigError(ValueError):
    """Akkor dob, ha indítási biztonsági validáció meghiúsul."""


_REQUIRED_SECURITY_FIELDS = (
    "cookie_samesite",
    "cookie_secure",
    "trusted_hosts",
    "rate_limit_login_per_minute",
    "redis_url",
    "access_ttl_min",
    "refresh_ttl_days",
    "refresh_ttl_session_hours",
)


def validate_basic_security_config(settings: object) -> None:
    """Alap security config shape validáció.

    Cél: a későbbi guard-ok ne maszkoljanak el egyszerű konfigurációs hiányokat.
    Ez a guard csak azt ellenőrzi, hogy a szükséges mezők egyáltalán léteznek.
    """
    if settings is None:
        raise SecurityConfigError("security settings objektum hiányzik.")

    missing = [name for name in _REQUIRED_SECURITY_FIELDS if not hasattr(settings, name)]
    if missing:
        raise SecurityConfigError(
            "Hiányzó security konfigurációs mezők: "
            f"{', '.join(sorted(missing))}. "
            "Egészítsd ki a settings objektumot az indulás előtt."
        )


def validate_jwt_config_presence_and_format(settings: object, env: str) -> str:
    """JWT konfiguráció megléte és alap formája.

    Ez a guard csak a mező jelenlétét és a minimális, strukturális elvárásokat
    ellenőrzi. Az entrópia ellenőrzése külön guard-ban történik.
    """
    secret = getattr(settings, "jwt_secret", "")
    normalized_secret = str(secret or "").strip()
    if not normalized_secret:
        raise SecurityConfigError(
            "jwt_secret nincs beállítva. "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(normalized_secret) < 32:
        raise SecurityConfigError(
            f"jwt_secret túl rövid ({len(normalized_secret)} karakter); minimum 32 szükséges. "
            "Generálj egyet: openssl rand -hex 64"
        )

    if env != "prod":
        return normalized_secret

    env_secret = (os.getenv("JWT_SECRET") or "").strip()
    if not env_secret:
        raise SecurityConfigError(
            "Production környezetben a JWT_SECRET környezeti változó megadása kötelező. "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(env_secret) < 64:
        raise SecurityConfigError(
            f"Production JWT_SECRET legalább 64 karakter hosszú kell legyen "
            f"(jelenlegi: {len(env_secret)} karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )
    return env_secret


# ---------------------------------------------------------------------------
# JWT secret guard
# ---------------------------------------------------------------------------


def validate_jwt_secret_strength(secret: str, env: str) -> None:
    """JWT secret erőssége / entrópiája.

    A szerkezeti követelmények ellenőrzése a ``validate_jwt_config_presence_and_format``
    guard feladata; itt csak az erősség marad.
    """
    if env != "prod":
        return
    if len(set(secret)) < 16:
        raise SecurityConfigError(
            "JWT_SECRET entrópiája elégtelen (túl sok ismétlődő karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )


# ---------------------------------------------------------------------------
# Cookie policy guard
# ---------------------------------------------------------------------------

_VALID_SAMESITE_VALUES = {"lax", "strict", "none"}


def validate_secure_refresh_cookie_policy(settings: object, env: str) -> None:
    """Cookie biztonsági flagek konzisztenciájának ellenőrzése.

    - cookie_samesite csak "lax", "strict" vagy "none" lehet.
    - SameSite=None kötelezően Secure=True-val kell párosulnia (böngésző elutasítja különben).
    - Production: cookie_secure=True kötelező (HTTPS).
    """
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

    if env == "prod" and not secure:
        raise SecurityConfigError(
            "cookie_secure=False production környezetben nem engedélyezett. "
            "Az alkalmazás csak HTTPS-en keresztül üzemeltethető production-ben."
        )


# ---------------------------------------------------------------------------
# CSRF guard
# ---------------------------------------------------------------------------

_CSRF_DISABLED_TRUTHY = frozenset({"1", "true", "yes", "on"})


def validate_csrf_policy(env: str) -> None:
    """CSRF védelem nem kapcsolható ki production-ben.

    Ha DISABLE_CSRF igaz értékre van állítva production-ben, az alkalmazás nem indulhat el.
    """
    if env != "prod":
        return
    raw = (os.environ.get("DISABLE_CSRF") or "").strip().lower()
    if raw in _CSRF_DISABLED_TRUTHY:
        raise SecurityConfigError(
            "DISABLE_CSRF be van kapcsolva production környezetben (engedélyezett értékek: 1, true, yes, on). "
            "Távolítsd el a változót vagy állítsd üresre."
        )


# ---------------------------------------------------------------------------
# Trusted hosts guard
# ---------------------------------------------------------------------------


def validate_trusted_hosts(settings: object, env: str) -> None:
    """TrustedHost middleware konfiguráció ellenőrzése.

    Production: trusted_hosts kötelező, wildcard '*' nem engedélyezett.
    """
    hosts_raw = (getattr(settings, "trusted_hosts", "") or "").strip()

    if env == "prod":
        if not hosts_raw:
            raise SecurityConfigError(
                "trusted_hosts production-ben kötelező. "
                "Példa: trusted_hosts=example.com,api.example.com"
            )
        hosts = [h.strip() for h in hosts_raw.split(",") if h.strip()]
        if "*" in hosts:
            raise SecurityConfigError(
                "Wildcard '*' trusted_hosts production-ben nem engedélyezett. "
                "Add meg az engedélyezett hostokat explicit módon."
            )


# ---------------------------------------------------------------------------
# Rate limit guard
# ---------------------------------------------------------------------------

_MAX_REASONABLE_RATE_LIMIT = 200


def validate_rate_limit_config(settings: object, env: str) -> None:
    """Rate limit konfiguráció szanity-check-je.

    - rate_limit_login_per_minute pozitív egész szám kell legyen.
    - Production: max 30/perc a login végponton (védi a brute-force ellen).
    """
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

    if env == "prod" and limit > 30:
        raise SecurityConfigError(
            f"rate_limit_login_per_minute={limit} production-ben túl magas "
            "(ajánlott maximum login végponton: 30/perc). "
            "Brute-force védelem érdekében csökkentsd le."
        )


# ---------------------------------------------------------------------------
# Redis / megosztott state guard (rate limit + allowlist)
# ---------------------------------------------------------------------------


def validate_production_redis_url(settings: object, env: str) -> None:
    """Production: Redis URL kötelező a megosztott rate limit tárolóhoz és allowlisthez.

    A slowapi limiter és a token allowlist in-memory módban nem biztonságos
    több web-process mellett; élesben egy közös Redis példány szükséges.
    """
    if env != "prod":
        return
    url = (getattr(settings, "redis_url", "") or "").strip()
    if not url:
        raise SecurityConfigError(
            "redis_url production-ben kötelező: a globális rate limiter és a token allowlist "
            "megosztott tárolót igényel (több worker / több példány esetén in-memory nem megfelelő)."
        )


# ---------------------------------------------------------------------------
# Refresh token TTL guard
# ---------------------------------------------------------------------------

_MAX_PROD_ACCESS_TTL_MIN = 60
_MAX_PROD_REFRESH_TTL_DAYS = 90


def validate_refresh_token_policy(settings: object, env: str) -> None:
    """Refresh token TTL konzisztenciájának ellenőrzése.

    - access_ttl_min < refresh_ttl_days * 24 * 60 (access nem lehet hosszabb a refresh-nél)
    - Production: access max 60 perc, refresh max 90 nap
    - Minden TTL értéknek pozitívnak kell lennie
    """
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

    if env == "prod":
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


# ---------------------------------------------------------------------------
# Összefoglaló belépési pont
# ---------------------------------------------------------------------------


def run_kernel_security_guards(settings: object, env: str) -> None:
    """Futtatja az összes kernel-szintű biztonsági guard-ot.

    Az alkalmazás indulása előtt hívd meg ezt a függvényt.
    Bármilyen hiba esetén SecurityConfigError-t dob egyértelmű üzenettel.

    Kernel guard sorrend:
      1. alap config shape
      2. JWT config megléte és formája
      3. JWT secret erőssége / entrópiája
      4. secure refresh cookie policy
      5. trusted hosts policy
      6. CSRF policy
      7. rate limit policy
      8. shared state / TTL hardening
    """
    validate_basic_security_config(settings)
    secret = validate_jwt_config_presence_and_format(settings, env)
    validate_jwt_secret_strength(secret, env)
    validate_secure_refresh_cookie_policy(settings, env)
    validate_trusted_hosts(settings, env)
    validate_csrf_policy(env)
    validate_rate_limit_config(settings, env)
    validate_production_redis_url(settings, env)
    validate_refresh_token_policy(settings, env)


__all__ = [
    "SecurityConfigError",
    "validate_basic_security_config",
    "validate_jwt_config_presence_and_format",
    "validate_jwt_secret_strength",
    "run_kernel_security_guards",
    "validate_secure_refresh_cookie_policy",
    "validate_csrf_policy",
    "validate_production_redis_url",
    "validate_rate_limit_config",
    "validate_refresh_token_policy",
    "validate_trusted_hosts",
]
