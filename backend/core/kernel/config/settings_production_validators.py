# backend/core/kernel/config/settings_production_validators.py
# Feladat: Production környezetre vonatkozó kritikus settings validációkat tartalmazza. Ellenőrzi a JWT secretet, HTTPS/CORS/trusted host szabályokat, SMTP és database kötelező mezőket, Redis jelenlétet és debug bypass env-ek tiltását. Staging JWT_SECRET policyt a startup guard érvényesít. A base.py közvetetten hívja, ezért ez a config réteg production hardening helper modulja.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os
from typing import Any

from core.kernel.config.environment import is_production_env, normalize_app_env
from core.kernel.config.settings_constants import DOMAIN_LABEL_RE


def validate_production_security_settings(settings: Any, *, env: str | None = None) -> None:
    effective_env = normalize_app_env(env)
    if not is_production_env(effective_env):
        return

    origins = [o.strip() for o in (settings.cors_origins or "").split(",") if o.strip()]
    _validate_production_jwt_secret()
    _require_production_field(settings.frontend_base_url, "frontend_base_url")
    _validate_production_smtp(settings)
    _require_production_field(settings.database_url, "database_url")
    if not settings.cookie_secure:
        raise ValueError("cookie_secure nem lehet False production környezetben.")
    _validate_production_cors(origins)
    _validate_production_trusted_hosts(settings.trusted_hosts)
    _validate_production_tenant_base_domain(settings.tenant_base_domain)
    if (getattr(settings, "password_security_level", "standard") or "").strip().lower() == "basic":
        raise ValueError(
            "password_security_level='basic' production-ben nem engedélyezett. "
            "Legalább 'standard' szintet kell használni."
        )
    rate_limit_login_per_minute = int(getattr(settings, "rate_limit_login_per_minute", 0) or 0)
    if rate_limit_login_per_minute > 30:
        raise ValueError(
            f"rate_limit_login_per_minute={rate_limit_login_per_minute} "
            "production-ben túl magas (ajánlott maximum: 30/perc)."
        )
    _validate_production_jwt_contract(settings.jwt_issuer, settings.jwt_audience)
    if not (settings.redis_url or "").strip():
        raise ValueError(
            "redis_url kötelező production környezetben (rate limit megosztott tároló és token allowlist)."
        )
    _validate_production_debug_bypass_env()
    access_ttl_min = int(getattr(settings, "access_ttl_min", 0) or 0)
    if access_ttl_min > 60:
        raise ValueError(
            f"access_ttl_min={access_ttl_min} perc production-ben túl hosszú "
            "(ajánlott maximum: 60 perc)."
        )


def _require_production_field(value: Any, field_name: str) -> None:
    if not str(value or "").strip():
        raise ValueError(f"{field_name} kötelező production környezetben.")


def _validate_production_jwt_secret() -> None:
    env_secret = (os.getenv("JWT_SECRET") or "").strip()
    if not env_secret:
        raise ValueError(
            "Production környezetben a JWT_SECRET környezeti változó megadása kötelező. "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(env_secret) < 64:
        raise ValueError(
            f"Production JWT_SECRET legalább 64 karakter hosszú kell legyen "
            f"(jelenlegi: {len(env_secret)} karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )
    if len(set(env_secret)) < 16:
        raise ValueError(
            "JWT_SECRET entrópiája elégtelen production-ben (túl sok ismétlődő karakter). "
            "Generálj egyet: openssl rand -hex 64"
        )


def _validate_production_smtp(settings: Any) -> None:
    _require_production_field(settings.smtp_password, "smtp_password")
    _require_production_field(settings.smtp_host, "smtp_host")
    _require_production_field(settings.smtp_user, "smtp_user")
    _require_production_field(settings.smtp_from_email, "smtp_from_email")
    _require_production_field(settings.smtp_from_name, "smtp_from_name")


def _validate_production_cors(origins: list[str]) -> None:
    if "*" in origins:
        raise ValueError("CORS wildcard origin ('*') nem engedélyezett production környezetben.")
    if any(origin.startswith("http://") for origin in origins):
        raise ValueError("Production CORS origin-ekhez kötelező a HTTPS.")


def _validate_production_trusted_hosts(raw_hosts: str) -> None:
    if not (raw_hosts or "").strip():
        raise ValueError("trusted_hosts kötelező production környezetben.")
    hosts = [h.strip() for h in (raw_hosts or "").split(",") if h.strip()]
    if "*" in hosts:
        raise ValueError("Wildcard '*' trusted_hosts production-ben nem engedélyezett.")


def _validate_production_tenant_base_domain(raw_domain: str) -> None:
    base_domain = (raw_domain or "").strip().lower()
    if not base_domain:
        raise ValueError("tenant_base_domain kötelező production környezetben.")
    if base_domain in {"local", "localhost"}:
        raise ValueError("tenant_base_domain='local/localhost' production-ben nem engedélyezett.")
    if any(token in base_domain for token in ("*", "/", "\\", ":", " ")):
        raise ValueError("tenant_base_domain production-ben csak tiszta hostname lehet.")
    labels = [part for part in base_domain.split(".") if part]
    if len(labels) < 2:
        raise ValueError(
            "tenant_base_domain production-ben teljes domain kell legyen (pl. app.example.com)."
        )
    if any(not DOMAIN_LABEL_RE.fullmatch(label) for label in labels):
        raise ValueError("tenant_base_domain nem RFC-kompatibilis hostname formátum.")


def _validate_production_jwt_contract(raw_issuer: str, raw_audience: str) -> None:
    issuer = (raw_issuer or "").strip()
    if len(issuer) < 3:
        raise ValueError(
            f"jwt_issuer túl rövid ({issuer!r}). Legalább 3 karakteres azonosítót adj meg."
        )
    audience = (raw_audience or "").strip()
    if not audience:
        raise ValueError(
            "jwt_audience production-ben kötelező (egyértelmű API vagy erőforrás azonosító, pl. https://api.example.com)."
        )
    if audience == issuer:
        raise ValueError(
            "jwt_audience és jwt_issuer nem lehet azonos. Használj különböző iss és aud értékeket."
        )


def _validate_production_debug_bypass_env() -> None:
    if (os.getenv("DISABLE_CSRF") or "").strip():
        raise ValueError(
            "DISABLE_CSRF production-ben nem lehet beállítva. "
            "Távolítsd el az env-ből (ne 0-ra állítsd, hanem töröld)."
        )
    if (os.getenv("BILLING_DEBUG_ROUTES_ENABLED") or "").strip():
        raise ValueError(
            "BILLING_DEBUG_ROUTES_ENABLED production-ben nem lehet beállítva. "
            "A debug route-ok maradjanak rejtve."
        )
    if (os.getenv("BILLING_DISABLED") or "").strip():
        raise ValueError(
            "BILLING_DISABLED production-ben nem lehet beállítva. "
            "Ez megkerülheti a kérdéskeret-védelmet."
        )
    billing_provider = (os.getenv("BILLING_PROVIDER") or "manual").strip().lower()
    if billing_provider in {"simulated", "stripe_test"}:
        raise ValueError(
            f"BILLING_PROVIDER={billing_provider!r} production-ben nem engedélyezett. "
            "Amíg nincs éles payment provider, manual módot használj."
        )
    billing_mode = (os.getenv("BILLING_MODE") or "manual").strip().lower()
    if billing_mode != "manual":
        raise ValueError(
            f"BILLING_MODE={billing_mode!r} production-ben nem engedélyezett. "
            "Állítsd BILLING_MODE=manual értékre."
        )
    pii_legacy_plaintext = (os.getenv("PII_ALLOW_LEGACY_PLAINTEXT_READ") or "").strip().lower()
    if pii_legacy_plaintext in {"1", "true", "yes", "on"}:
        raise ValueError(
            "PII_ALLOW_LEGACY_PLAINTEXT_READ production-ben nem engedélyezett. "
            "Futtasd le a PII migrációt, majd állítsd false értékre."
        )
__all__ = ["validate_production_security_settings"]
