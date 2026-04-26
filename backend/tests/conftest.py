"""
Minimális, szülő conftest minden ``tests/`` gyűjtéshez.

Cél: a ``pytest tests/unit`` futtatáskor ne töltődjön be FastAPI app factory,
session-scoped ``app``, vagy PostgreSQL bootstrap – ezek a
``tests/integration/conftest.py``-ban vannak.

Fixture-ök és HTTP/DB specifikus mockok: ``tests/integration/conftest.py``.
"""
from __future__ import annotations

import os

# Izolált unit gyűjtéshez: ne hiányozzanak env-ek import előtt
os.environ.setdefault("RATE_LIMIT_LOGIN_PER_MINUTE", "100")
os.environ.setdefault("DISABLE_CSRF", "1")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("QDRANT_API_KEY", "")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-api-key")

from unittest.mock import MagicMock

# --- Mock service osztályok (integration + néhány unit auth teszt) ---


class MockLoginService:
    def __init__(self):
        self.result = None
        self.user_repository = None
        self.raise_2fa_too_many = False

    def login(self, inp):
        if self.raise_2fa_too_many and getattr(inp, "pending_token", None) and getattr(inp, "two_factor_code", None):
            from core.capabilities.auth.exceptions import TwoFactorTooManyAttemptsError

            raise TwoFactorTooManyAttemptsError()
        return self.result


class MockRefreshService:
    def __init__(self):
        self.result = None
        self.verify_payload = {"sub": "1", "typ": "refresh"}
        self.tokens = MagicMock()
        self.tokens.verify.side_effect = lambda rt: self.verify_payload

    def refresh(self, refresh_token: str, ip=None, ua=None, tenant=None, **kwargs):
        from core.capabilities.auth.service.refresh_result import (
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


__all__ = ["MockLoginService", "MockLogoutService", "MockRefreshService"]
