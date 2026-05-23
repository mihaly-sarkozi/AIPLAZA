"""
Minimális, szülő conftest minden ``tests/`` gyűjtéshez.

Cél: a ``pytest tests/unit`` futtatáskor ne töltődjön be FastAPI app factory,
session-scoped ``app``, vagy PostgreSQL bootstrap – ezek a
``tests/integration/conftest.py``-ban vannak.

Fixture-ök és HTTP/DB specifikus mockok: ``tests/integration/conftest.py``.
"""
from __future__ import annotations

import os
import pytest

# Izolált unit gyűjtéshez: ne hiányozzanak env-ek import előtt
_TEST_ENV_DEFAULTS = {
    "APP_ENV": "test",
    "JWT_SECRET": "test-secret-with-enough-length-01234567890123456789",
    "JWT_ISSUER": "aiplaza-test-issuer",
    "JWT_AUDIENCE": "aiplaza-test-api",
    "RATE_LIMIT_LOGIN_PER_MINUTE": "100",
    "DISABLE_CSRF": "1",
    "QDRANT_URL": "http://localhost:6333",
    "QDRANT_API_KEY": "test-qdrant-key",
    "OPENAI_API_KEY": "test-openai-api-key",
    "APP_NAME": "AIPLAZA Test",
    "APP_DESCRIPTION": "Unit test settings",
    "APP_VERSION": "test",
    "API_HOST": "127.0.0.1",
    "API_PORT": "8000",
    "CORS_ORIGINS": "http://localhost:3000",
    "FRONTEND_BASE_URL": "http://localhost:3000",
    "TENANT_BASE_DOMAIN": "app.test",
    "INSTALL_HOST": "app.test",
    "SINGLE_TENANT_SLUG": "demo",
    "TRUSTED_HOSTS": "localhost,127.0.0.1,app.test,*.app.test",
    "DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "DATABASE_POOL_PRE_PING": "false",
    "METRICS_ALLOWED_IPS": "127.0.0.1",
    "LOG_LEVEL": "INFO",
    "COOKIE_SECURE": "false",
    "PLATFORM_ADMIN_ALLOWED_IPS": "127.0.0.1/32",
    "CHAT_PROVIDER": "openai",
    "CHAT_MODEL": "gpt-4o-mini",
    "OLLAMA_URL": "http://localhost:11434",
    "OBJECT_STORAGE_ENDPOINT": "http://localhost:9000",
    "OBJECT_STORAGE_BUCKET": "aiplaza-test",
    "REDIS_URL": "",
    "SMTP_HOST": "localhost",
    "SMTP_USER": "test",
    "SMTP_PASSWORD": "test",
    "SMTP_FROM_EMAIL": "noreply@example.test",
    "INVOICE_ISSUER_NAME": "Test Issuer",
    "INVOICE_ISSUER_TAX_ID": "12345678-1-12",
    "INVOICE_ISSUER_ADDRESS_LINE": "Test utca 1.",
    "INVOICE_ISSUER_POSTAL_CODE": "1111",
    "INVOICE_ISSUER_CITY": "Budapest",
    "INVOICE_ISSUER_REGION": "HU-BU",
    "INVOICE_ISSUER_COUNTRY": "HU",
    "INVOICE_ISSUER_PHONE": "+3610000000",
    "INVOICE_ISSUER_WEBSITE": "https://example.test",
    "INVOICE_ISSUER_EMAIL": "billing@example.test",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)

from unittest.mock import MagicMock

# --- Mock service osztályok (integration + néhány unit auth teszt) ---


class MockLoginService:
    def __init__(self):
        self.result = None
        self.user_repository = None
        self.raise_2fa_too_many = False

    def login(self, inp):
        if self.raise_2fa_too_many and getattr(inp, "pending_token", None) and getattr(inp, "two_factor_code", None):
            from core.modules.auth.domain.exceptions import TwoFactorTooManyAttemptsError

            raise TwoFactorTooManyAttemptsError()
        return self.result


class MockRefreshService:
    def __init__(self):
        self.result = None
        self.verify_payload = {"sub": "1", "typ": "refresh"}
        self.tokens = MagicMock()
        self.tokens.verify.side_effect = lambda rt: self.verify_payload

    def refresh(self, refresh_token: str, ip=None, ua=None, tenant=None, **kwargs):
        from core.modules.auth.use_cases.refresh_result import (
            RefreshFailed,
            RefreshFailReason,
            RefreshSuccess,
        )

        r = self.result
        if r is None:
            return RefreshFailed(RefreshFailReason.UNKNOWN_SESSION)
        if isinstance(r, (RefreshFailed, RefreshSuccess)):
            return r
        # Régi integration tesztek: (access, refresh, access_jti, user) tuple
        if isinstance(r, tuple) and len(r) == 4:
            access, new_refresh, access_jti, user = r
            return RefreshSuccess(
                access_token=access,
                refresh_token=new_refresh,
                access_jti=access_jti,
                user=user,
                auto_login=False,
            )
        return r


class MockLogoutService:
    def __init__(self):
        self.result = True

    def logout(self, refresh_token: str, ip=None, ua=None, *, tenant=None, **kwargs):
        return self.result


@pytest.fixture(autouse=True)
def test_env(monkeypatch: pytest.MonkeyPatch):
    for key, value in _TEST_ENV_DEFAULTS.items():
        monkeypatch.setenv(key, value)
    yield


__all__ = ["MockLoginService", "MockLogoutService", "MockRefreshService"]
