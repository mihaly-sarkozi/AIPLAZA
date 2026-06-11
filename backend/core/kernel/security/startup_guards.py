# backend/core/kernel/security/startup_guards.py
# Feladat: Kernel-szintű technikai security startup guardok orchestrátora. Ellenőrzi az alap security settings shape-et, majd delegál a JWT, cookie, HTTP, rate limit, tenant/demo és token TTL guard modulokra. Core startup security komponens, amely hibás konfigurációval nem engedi elindulni az alkalmazást.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.security.cookie_guards import validate_secure_refresh_cookie_policy
from core.kernel.config.settings_production_validators import validate_production_security_settings
from core.kernel.security.errors import SecurityConfigError
from core.kernel.security.http_guards import (
    validate_cors_origin_regex_policy,
    validate_csrf_policy,
    validate_trusted_hosts,
)
from core.kernel.security.jwt_guards import (
    validate_jwt_config_presence_and_format,
    validate_jwt_secret_strength,
)
from core.kernel.security.rate_limit_guards import (
    validate_production_redis_url,
    validate_rate_limit_config,
)
from core.kernel.security.tenant_guards import (
    validate_billing_provider_hardening,
    validate_demo_signup_hardening,
    validate_object_storage_hardening,
    validate_pii_legacy_plaintext_hardening,
)
from core.kernel.security.token_ttl_guards import validate_refresh_token_policy


# Futtatja az összes kernel-szintű biztonsági guard-ot.
def run_kernel_security_guards(settings: object, env: str) -> None:
    _validate_basic_security_config(settings)
    try:
        validate_production_security_settings(settings, env=env)
    except ValueError as exc:
        raise SecurityConfigError(str(exc)) from exc
    secret = validate_jwt_config_presence_and_format(settings, env)
    validate_jwt_secret_strength(secret, env)
    validate_secure_refresh_cookie_policy(settings, env)
    validate_trusted_hosts(settings, env)
    validate_csrf_policy(env)
    validate_rate_limit_config(settings, env)
    validate_cors_origin_regex_policy(settings, env)
    validate_production_redis_url(settings, env)
    validate_billing_provider_hardening(env)
    validate_object_storage_hardening(settings, env)
    validate_pii_legacy_plaintext_hardening(env)
    validate_demo_signup_hardening(settings, env)
    validate_refresh_token_policy(settings, env)


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


def _validate_basic_security_config(settings: object) -> None:
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


__all__ = [
    "SecurityConfigError",
    "run_kernel_security_guards",
]
