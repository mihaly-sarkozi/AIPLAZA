"""Biztonsági indítási orchestrátor.

Ez a modul fogja össze a kernel szintű és a platform/auth szintű biztonsági
guard-okat, és egyetlen belépési pontot biztosít az alkalmazás indítása előtt
futtatandó összes security validációhoz.

Használat (app_factory.py-ban):

    from core.kernel.security.security_bootstrap import assert_security_ready
    assert_security_ready(settings, env=env)

A guard-ok végrehajtási sorrendje:
  1. alap konfiguráció megléte
  2. JWT konfiguráció megléte és formája
  3. JWT secret erőssége / entrópiája
  4. issuer / audience policy
  5. secure refresh cookie policy
  6. trusted hosts / domain policy
  7. CSRF policy
  8. rate limit policy
  9. további hardening guard-ok (Redis URL, TTL, 2FA, jelszó policy, invite TTL)

Bármely guard meghiúsulása esetén SecurityConfigError-t dob (és naplózza
CRITICAL szinten), hogy az alkalmazás ne induljon hibás konfigurációval.
"""
from __future__ import annotations

import logging
import os

from core.kernel.security.startup_guards import (
    SecurityConfigError,
    validate_basic_security_config,
    validate_csrf_policy,
    validate_jwt_config_presence_and_format,
    validate_jwt_secret_strength,
    validate_production_redis_url,
    validate_rate_limit_config,
    validate_refresh_token_policy,
    validate_secure_refresh_cookie_policy,
    validate_trusted_hosts,
)

_log = logging.getLogger(__name__)


def validate_all_security_config(settings: object, *, env: str) -> None:
    """Futtatja az összes security guard-ot a megadott env-ben.

    A guard-ok tudatosan diagnosztikai sorrendben futnak, hogy a célzott tesztek
    és a production startup hibák a valódi problémára mutassanak.
    """
    try:
        from core.platform.auth.security_policy import (
            SecurityPolicyError,
            run_non_jwt_auth_policy_guards,
            validate_jwt_issuer_audience,
        )
    except ImportError as exc:
        raise SecurityConfigError(
            f"Nem sikerült betölteni a platform auth policy guard-okat: {exc}"
        ) from exc

    try:
        # 1. alap konfiguráció megléte
        validate_basic_security_config(settings)
        # 2. JWT konfiguráció megléte és formája
        secret = validate_jwt_config_presence_and_format(settings, env)
        # 3. JWT secret erőssége / entrópiája
        validate_jwt_secret_strength(secret, env)
        # 4. issuer / audience policy
        validate_jwt_issuer_audience(settings, env)
        # 5. secure refresh cookie policy
        validate_secure_refresh_cookie_policy(settings, env)
        # 6. trusted hosts / domain policy
        validate_trusted_hosts(settings, env)
        # 7. CSRF policy
        validate_csrf_policy(env)
        # 8. rate limit policy
        validate_rate_limit_config(settings, env)

        # További production hardening guard-ok a fenti, kötelező diagnosztikai
        # sorrend után futnak.
        validate_production_redis_url(settings, env)
        validate_refresh_token_policy(settings, env)
        run_non_jwt_auth_policy_guards(settings, env)
    except SecurityPolicyError as exc:
        raise SecurityConfigError(str(exc)) from exc


def assert_security_ready(settings: object, *, env: str | None = None) -> None:
    """Ellenőrzi, hogy a biztonsági konfiguráció megfelelő az adott környezetben.

    Hiba esetén CRITICAL szinten naplóz, majd újra dobja a kivételt, hogy az
    alkalmazás indítása megszakadjon. Ez egyértelműbb hibajelzést ad, mint egy
    rejtett, késői ConfigError.

    Args:
        settings: Az alkalmazás konfiguráció objektuma (BaseConfig példány).
        env: A futtatási környezet ("dev" / "prod"). Ha None, APP_ENV env var-ból olvas.
    """
    effective_env = env or (os.getenv("APP_ENV") or "dev").strip().lower()

    try:
        validate_all_security_config(settings, env=effective_env)
    except (SecurityConfigError, ValueError) as exc:
        _log.critical(
            "BIZTONSÁGI KONFIGURÁCIÓ HIBA [env=%s]: %s\n"
            "Az alkalmazás ezzel a konfigurációval nem indítható el.\n"
            "Javítsd a konfigurációt és indítsd újra a rendszert.",
            effective_env,
            exc,
        )
        raise

    _log.info(
        "Biztonsági konfiguráció sikeresen validálva (env=%s).",
        effective_env,
    )


__all__ = [
    "SecurityConfigError",
    "assert_security_ready",
    "validate_all_security_config",
]
