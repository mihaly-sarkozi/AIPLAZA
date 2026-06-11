# backend/core/kernel/security/tenant_guards.py
# Feladat: Tenant/demo/signup, billing és PII production hardening guardokat tartalmaz. Éles környezetben megköveteli a demo signup captcha/email/MX védelmeket, tiltja a nem éles billing módokat és a legacy plaintext PII olvasást. Core startup security guard a platform tenant és üzemi kockázatokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import os

from core.kernel.config.environment import is_deployed_env, is_production_env
from core.kernel.security.errors import SecurityConfigError
from core.kernel.runtime.instance_role import InstanceRole, get_instance_role


def validate_demo_signup_hardening(settings: object, env: str) -> None:
    if not is_production_env(env):
        return
    if not bool(getattr(settings, "demo_signups_enabled", True)):
        return
    if not bool(getattr(settings, "demo_signup_require_captcha", False)):
        raise SecurityConfigError(
            "Production-ben a demo signup captcha kötelező (demo_signup_require_captcha=true)."
        )
    provider = str(getattr(settings, "demo_signup_captcha_provider", "none") or "none").strip().lower()
    if provider not in {"turnstile", "recaptcha"}:
        raise SecurityConfigError(
            "Production-ben demo signup captcha provider kötelező (turnstile vagy recaptcha)."
        )
    secret = str(getattr(settings, "demo_signup_captcha_secret", "") or "").strip()
    if not secret:
        raise SecurityConfigError("Production-ben demo signup captcha secret kötelező.")
    if not bool(getattr(settings, "demo_signup_require_email_verification", True)):
        raise SecurityConfigError(
            "Production-ben a demo signup email verifikáció nem kapcsolható ki."
        )
    if bool(getattr(settings, "demo_signup_expose_login_token_in_response", False)):
        raise SecurityConfigError(
            "Production-ben demo login token nem adható vissza signup válaszban (demo_signup_expose_login_token_in_response=false)."
        )
    if not bool(getattr(settings, "demo_signup_block_disposable_emails", True)):
        raise SecurityConfigError(
            "Production-ben disposable email tiltás kötelező a demo signupnál."
        )
    if not bool(getattr(settings, "demo_signup_require_mx", True)):
        raise SecurityConfigError("Production-ben MX ellenőrzés kötelező a demo signupnál.")


def validate_billing_provider_hardening(env: str) -> None:
    if not is_production_env(env):
        return
    provider = (os.getenv("BILLING_PROVIDER") or "manual").strip().lower()
    if provider in {"simulated", "stripe_test"}:
        raise SecurityConfigError(
            f"BILLING_PROVIDER={provider!r} production-ben nem engedélyezett. "
            "Használj manual módot, amíg nincs éles payment provider."
        )
    billing_mode = (os.getenv("BILLING_MODE") or "manual").strip().lower()
    if billing_mode != "manual":
        raise SecurityConfigError(
            f"BILLING_MODE={billing_mode!r} production-ben nem engedélyezett. "
            "Állítsd BILLING_MODE=manual értékre."
        )


def validate_pii_legacy_plaintext_hardening(env: str) -> None:
    if not is_production_env(env):
        return
    raw = (os.getenv("PII_ALLOW_LEGACY_PLAINTEXT_READ") or "").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        raise SecurityConfigError(
            "PII_ALLOW_LEGACY_PLAINTEXT_READ production-ben nem engedélyezett. "
            "Futtasd le a PII migrációt és állítsd false értékre."
        )


def validate_object_storage_hardening(settings: object, env: str) -> None:
    if not is_deployed_env(env):
        return
    if not bool(getattr(settings, "object_storage_enabled", True)):
        raise SecurityConfigError("Staging/production környezetben object_storage_enabled=true kötelező.")
    provider = str(getattr(settings, "object_storage_provider", "") or "").strip().lower()
    if provider != "s3_compatible":
        raise SecurityConfigError(
            "Staging/production környezetben csak explicit S3/MinIO/GCS-kompatibilis object storage provider engedélyezett "
            "(object_storage_provider=s3_compatible)."
        )
    endpoint = str(getattr(settings, "object_storage_endpoint", "") or "").strip()
    bucket = str(getattr(settings, "object_storage_bucket", "") or "").strip()
    if not endpoint:
        raise SecurityConfigError("Staging/production környezetben object_storage_endpoint kötelező.")
    if not bucket:
        raise SecurityConfigError("Staging/production környezetben object_storage_bucket kötelező.")
    if not bool(getattr(settings, "object_storage_secure", False)):
        raise SecurityConfigError(
            "Staging/production környezetben object_storage_secure=true (TLS) kötelező az object storage kapcsolathoz."
        )
    access_key = str(getattr(settings, "object_storage_access_key", "") or "").strip()
    secret_key = str(getattr(settings, "object_storage_secret_key", "") or "").strip()
    if not access_key or not secret_key:
        raise SecurityConfigError(
            "Staging/production környezetben object_storage_access_key és object_storage_secret_key kötelező."
        )


__all__ = [
    "validate_billing_provider_hardening",
    "validate_demo_signup_hardening",
    "validate_object_storage_hardening",
    "validate_pii_legacy_plaintext_hardening",
]
