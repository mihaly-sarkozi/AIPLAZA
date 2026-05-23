# backend/core/kernel/security/security_startup_checks.py
# Feladat: Az összes indításkori security check közös orchestrátora. Kernel technikai guardokat és auth policy guardokat futtat, majd hibás konfiguráció esetén SecurityConfigErrorral megakadályozza az app indulását. Core startup security belépési pont, amelyet az app_factory hív.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging

from core.kernel.config.bootstrap_guards import (
    ConfigBootstrapError,
    validate_settings,
)
from core.kernel.config.environment import is_production_env, normalize_app_env
from core.kernel.logging.observability import log_structured_event
from core.kernel.security.auth_policy_guards import (
    SecurityPolicyError,
    run_auth_policy_guards,
)
from core.kernel.security.startup_guards import (
    SecurityConfigError,
    run_kernel_security_guards,
)

_log = logging.getLogger(__name__)


def run_security_startup_checks(settings: object, *, env: str | None = None) -> None:
    
    # A környezet beállítása 
    effective_env = normalize_app_env(env)

    # A biztonsági konfiguráció validálása
    try:
        validate_settings(settings, effective_env)

        # 1-3. kernel-szintű technikai security guard-ok
        run_kernel_security_guards(settings, effective_env)
        
        # 4. auth-hoz kapcsolódó indítási policy guard-ok
        run_auth_policy_guards(settings, effective_env)
        
    except SecurityPolicyError as exc:
        raise SecurityConfigError(str(exc)) from exc
    except (ConfigBootstrapError, SecurityConfigError, ValueError) as exc:
        _log.critical(
            "BIZTONSÁGI KONFIGURÁCIÓ HIBA [env=%s]: %s\n"
            "Az alkalmazás ezzel a konfigurációval nem indítható el.\n"
            "Javítsd a konfigurációt és indítsd újra a rendszert.",
            effective_env,
            exc,
        )
        raise

    _log_security_guard_status(settings, effective_env)
    _log.info("Biztonsági konfiguráció sikeresen validálva (env=%s).", effective_env)


def _log_security_guard_status(settings: object, env: str) -> None:
    """Secret nélküli, strukturált startup állapotlog a security guardokról."""
    import os

    production = is_production_env(env)
    jwt_secret_from_env = bool((os.getenv("JWT_SECRET") or "").strip())
    log_structured_event(
        "core.security.startup",
        "security_guards.validated",
        env=env,
        jwt_secret_env_required=env in {"test", "staging", "production"},
        jwt_secret_from_env=jwt_secret_from_env,
        jwt_audience_required=production,
        cookie_secure_required=env in {"staging", "production"},
        cookie_secure=bool(getattr(settings, "cookie_secure", False)),
        cors_wildcard_blocked=production,
        trusted_hosts_strict=production,
        redis_required=env in {"staging", "production"},
        redis_configured=bool(str(getattr(settings, "redis_url", "") or "").strip()),
        csrf_prod_guard_active=production,
        billing_debug_guard_active=production,
        pii_legacy_plaintext_guard_active=production,
        secrets_logged=False,
    )


__all__ = [
    "SecurityConfigError",
    "run_security_startup_checks",
]
