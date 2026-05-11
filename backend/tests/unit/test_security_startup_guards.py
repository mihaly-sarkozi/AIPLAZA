from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.kernel.security.security_bootstrap import assert_security_ready
from core.kernel.security.startup_guards import (
    SecurityConfigError,
    run_kernel_security_guards,
    validate_basic_security_config,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@contextmanager
def prod_env(**overrides: str):
    env = {"APP_ENV": "prod"}
    env.update({k: v for k, v in overrides.items() if v is not None})
    with patch.dict("os.environ", env, clear=True):
        yield


def _settings(**kwargs):
    base = dict(
        jwt_secret="0123456789abcdef" * 4,
        cookie_secure=True,
        cookie_samesite="lax",
        trusted_hosts="example.com,api.example.com",
        rate_limit_login_per_minute=30,
        redis_url="redis://redis:6379/0",
        tenant_base_domain="app.test",
        access_ttl_min=15,
        refresh_ttl_days=30,
        refresh_ttl_session_hours=24,
        jwt_issuer="AIPLAZA",
        jwt_audience="api.example.com",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_prod_bootstrap_fails_fast_without_jwt_secret():
    with prod_env(JWT_SECRET=""):
        with pytest.raises(SecurityConfigError, match="JWT_SECRET|jwt_secret"):
            run_kernel_security_guards(_settings(jwt_secret=""), "prod")


def test_prod_bootstrap_fails_when_jwt_secret_entropy_is_too_low():
    weak_secret = "x" * 64
    with prod_env(JWT_SECRET=weak_secret):
        with pytest.raises(SecurityConfigError, match="entrópiája elégtelen"):
            run_kernel_security_guards(_settings(jwt_secret=weak_secret), "prod")


def test_basic_security_config_reports_missing_fields_before_other_guards():
    with pytest.raises(SecurityConfigError, match="cookie_secure"):
        validate_basic_security_config(SimpleNamespace())


def test_prod_bootstrap_fails_without_secure_refresh_cookie():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="cookie_secure=False"):
            run_kernel_security_guards(_settings(cookie_secure=False), "prod")


def test_prod_bootstrap_fails_without_trusted_hosts():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="trusted_hosts"):
            run_kernel_security_guards(_settings(trusted_hosts=""), "prod")


def test_prod_bootstrap_fails_when_csrf_is_disabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, DISABLE_CSRF="1"):
        with pytest.raises(SecurityConfigError, match="DISABLE_CSRF"):
            run_kernel_security_guards(_settings(), "prod")


def test_prod_bootstrap_fails_when_rate_limit_is_too_high():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="rate_limit_login_per_minute"):
            run_kernel_security_guards(_settings(rate_limit_login_per_minute=60), "prod")


def test_security_bootstrap_wraps_domain_policy_errors():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="jwt_audience"):
            assert_security_ready(_settings(jwt_audience="AIPLAZA"), env="prod")


def test_prod_bootstrap_fails_when_simulated_billing_provider_enabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, BILLING_PROVIDER="simulated", BILLING_MODE="manual"):
        with pytest.raises(SecurityConfigError, match="BILLING_PROVIDER"):
            run_kernel_security_guards(_settings(), "prod")


def test_prod_bootstrap_fails_when_billing_mode_is_not_manual():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, BILLING_PROVIDER="manual", BILLING_MODE="auto"):
        with pytest.raises(SecurityConfigError, match="BILLING_MODE"):
            run_kernel_security_guards(_settings(), "prod")


def test_prod_bootstrap_fails_when_legacy_plaintext_pii_read_is_enabled():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4, PII_ALLOW_LEGACY_PLAINTEXT_READ="true"):
        with pytest.raises(SecurityConfigError, match="PII_ALLOW_LEGACY_PLAINTEXT_READ"):
            run_kernel_security_guards(_settings(), "prod")


def test_prod_bootstrap_fails_when_tenant_base_domain_is_local():
    with prod_env(JWT_SECRET="0123456789abcdef" * 4):
        with pytest.raises(SecurityConfigError, match="tenant_base_domain"):
            run_kernel_security_guards(_settings(tenant_base_domain="local"), "prod")
