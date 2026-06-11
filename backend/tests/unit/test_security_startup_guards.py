from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.kernel.config.base import BaseConfig
from core.kernel.security.security_startup_checks import run_security_startup_checks
from core.kernel.security.startup_guards import (
    SecurityConfigError,
    run_kernel_security_guards,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def _base_config_env(**overrides: str) -> dict[str, str]:
    env = {
        "APP_NAME": "AIPLAZA Test",
        "APP_DESCRIPTION": "Unit test settings",
        "APP_VERSION": "test",
        "API_HOST": "127.0.0.1",
        "API_PORT": "8000",
        "CORS_ORIGINS": "https://app.example.com",
        "TENANT_BASE_DOMAIN": "app.example.com",
        "INSTALL_HOST": "api.example.com",
        "SINGLE_TENANT_SLUG": "demo",
        "TRUSTED_HOSTS": "api.example.com,app.example.com",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "DATABASE_POOL_PRE_PING": "true",
        "METRICS_ALLOWED_IPS": "127.0.0.1",
        "LOG_LEVEL": "INFO",
        "JWT_ISSUER": "AIPLAZA",
        "JWT_AUDIENCE": "api.example.com",
        "COOKIE_SECURE": "true",
        "CHAT_PROVIDER": "ollama",
        "CHAT_MODEL": "qwen",
        "OLLAMA_URL": "http://localhost:11434",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_API_KEY": "",
        "OBJECT_STORAGE_ENDPOINT": "https://objects.example.com",
        "OBJECT_STORAGE_BUCKET": "aiplaza-test",
        "PLATFORM_ADMIN_ALLOWED_IPS": "127.0.0.1",
        "INVOICE_ISSUER_NAME": "AIPLAZA",
        "INVOICE_ISSUER_TAX_ID": "12345678-1-42",
        "INVOICE_ISSUER_ADDRESS_LINE": "Test street 1",
        "INVOICE_ISSUER_POSTAL_CODE": "1000",
        "INVOICE_ISSUER_CITY": "Budapest",
        "INVOICE_ISSUER_REGION": "Budapest",
        "INVOICE_ISSUER_COUNTRY": "HU",
        "INVOICE_ISSUER_PHONE": "+3610000000",
        "INVOICE_ISSUER_WEBSITE": "https://example.com",
        "INVOICE_ISSUER_EMAIL": "billing@example.com",
    }
    env.update(overrides)
    return env


@contextmanager
def prod_env(**overrides: str):
    env = {
        "APP_ENV": "production",
        "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
        "JWT_ISSUER": "AIPLAZA",
        "JWT_AUDIENCE": "api.example.com",
        "FRONTEND_BASE_URL": "https://app.example.com",
        "CORS_ORIGINS": "https://app.example.com",
        "TRUSTED_HOSTS": "app.example.com,api.example.com",
        "TENANT_BASE_DOMAIN": "app.example.com",
        "REDIS_URL": "redis://localhost:6379/0",
        "SMTP_HOST": "localhost",
        "SMTP_USER": "test",
        "SMTP_PASSWORD": "test",
        "SMTP_FROM_EMAIL": "noreply@example.com",
    }
    env.update({k: v for k, v in overrides.items() if v is not None})
    with patch.dict("os.environ", env, clear=True):
        yield


def _settings(**kwargs):
    base = dict(
        jwt_secret="0123456789abcdef" * 4,
        cookie_secure=True,
        cookie_samesite="lax",
        trusted_hosts="example.com,api.example.com",
        cors_origins="https://app.example.com",
        frontend_base_url="https://app.example.com",
        database_url="postgresql://test:test@localhost:5432/test",
        rate_limit_login_per_minute=30,
        redis_url="redis://redis:6379/0",
        tenant_base_domain="app.test",
        access_ttl_min=15,
        refresh_ttl_days=30,
        refresh_ttl_session_hours=24,
        jwt_issuer="AIPLAZA",
        jwt_audience="api.example.com",
        smtp_host="localhost",
        smtp_user="test",
        smtp_password="test",
        smtp_from_email="noreply@example.com",
        smtp_from_name="AIPLAZA Test",
        demo_signup_require_captcha=True,
        demo_signup_captcha_provider="turnstile",
        demo_signup_captcha_secret="test-secret",
        demo_signup_require_email_verification=True,
        demo_signup_expose_login_token_in_response=False,
        demo_signup_block_disposable_emails=True,
        demo_signup_require_mx=True,
        object_storage_enabled=True,
        object_storage_provider="s3_compatible",
        object_storage_endpoint="https://objects.example.com",
        object_storage_bucket="aiplaza-prod",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_prod_bootstrap_fails_fast_without_jwt_secret():
    with prod_env(JWT_SECRET=""):
        with pytest.raises(SecurityConfigError, match="JWT_SECRET|jwt_secret"):
            run_kernel_security_guards(_settings(jwt_secret=""), "production")


def test_prod_bootstrap_fails_when_jwt_secret_entropy_is_too_low():
    weak_secret = "x" * 64
    with prod_env(JWT_SECRET=weak_secret):
        with pytest.raises(SecurityConfigError, match="entrópiája elégtelen"):
            run_kernel_security_guards(_settings(jwt_secret=weak_secret), "production")


def test_basic_security_config_reports_missing_fields_before_other_guards():
    with pytest.raises(SecurityConfigError, match="cookie_secure"):
        run_kernel_security_guards(SimpleNamespace(), "dev")


def test_settings_load_does_not_run_production_dependency_guards():
    env = _base_config_env(
        APP_ENV="production",
        JWT_SECRET="weak",
        REDIS_URL="",
        SMTP_PASSWORD="",
        CORS_ORIGINS="*",
    )
    with patch.dict("os.environ", env, clear=True):
        settings = BaseConfig()

    assert settings.cors_origins == "*"
    assert settings.redis_url == ""


def test_test_env_does_not_require_production_jwt_secret_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    run_kernel_security_guards(_settings(jwt_secret="test-secret-value-with-enough-length"), "test")


def test_prod_bootstrap_fails_without_secure_refresh_cookie():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="cookie_secure"):
            run_kernel_security_guards(_settings(cookie_secure=False), "production")


def test_prod_bootstrap_fails_without_trusted_hosts():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="trusted_hosts"):
            run_kernel_security_guards(_settings(trusted_hosts=""), "production")


def test_prod_bootstrap_fails_with_cors_wildcard():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="CORS wildcard"):
            run_kernel_security_guards(_settings(cors_origins="*"), "production")


def test_prod_bootstrap_fails_when_csrf_is_disabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, DISABLE_CSRF="1"):
        with pytest.raises(SecurityConfigError, match="DISABLE_CSRF"):
            run_kernel_security_guards(_settings(), "production")


def test_prod_bootstrap_fails_when_rate_limit_is_too_high():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="rate_limit_login_per_minute"):
            run_kernel_security_guards(_settings(rate_limit_login_per_minute=60), "production")


def test_prod_bootstrap_fails_when_redis_missing_for_critical_runtime():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="redis_url"):
            run_kernel_security_guards(_settings(redis_url=""), "production")


def test_security_startup_checks_wraps_domain_policy_errors():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="jwt_audience"):
            run_security_startup_checks(_settings(jwt_audience="AIPLAZA"), env="production")


def test_prod_bootstrap_fails_when_simulated_billing_provider_enabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, BILLING_PROVIDER="simulated", BILLING_MODE="manual"):
        with pytest.raises(SecurityConfigError, match="BILLING_PROVIDER"):
            run_kernel_security_guards(_settings(), "production")


def test_prod_bootstrap_fails_when_billing_mode_is_not_manual():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, BILLING_PROVIDER="manual", BILLING_MODE="auto"):
        with pytest.raises(SecurityConfigError, match="BILLING_MODE"):
            run_kernel_security_guards(_settings(), "production")


def test_prod_bootstrap_fails_when_legacy_plaintext_pii_read_is_enabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, PII_ALLOW_LEGACY_PLAINTEXT_READ="true"):
        with pytest.raises(SecurityConfigError, match="PII_ALLOW_LEGACY_PLAINTEXT_READ"):
            run_kernel_security_guards(_settings(), "production")


def test_prod_bootstrap_fails_when_object_storage_is_disabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="object_storage_enabled"):
            run_kernel_security_guards(_settings(object_storage_enabled=False), "production")


def test_prod_bootstrap_fails_when_tenant_base_domain_is_local():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="tenant_base_domain"):
            run_kernel_security_guards(_settings(tenant_base_domain="local"), "production")
