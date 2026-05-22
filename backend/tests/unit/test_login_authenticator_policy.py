from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.modules.auth.domain.dto import LoginInput, LoginSuccess, LoginTwoFactorRequired, TenantAuthContext
from core.modules.auth.use_cases.login_service import LoginService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass
class _User:
    id: int
    email: str
    password_hash: str
    role: str
    is_active: bool = True
    security_version: int = 0


class _UserRepo:
    def __init__(self, user: _User) -> None:
        self.user = user

    def get_by_email(self, _email: str):
        return self.user

    def get_by_id(self, _user_id: int):
        return self.user

    def record_failed_login(self, _user_id: int, updated_by: int | None = None):
        return None

    def reset_failed_login(self, _user_id: int, updated_by: int | None = None):
        return None

    def increment_security_version(self, _user_id: int, updated_by: int | None = None):
        return None


class _SessionRepo:
    def invalidate_all_for_user(self, _user_id: int, updated_by: int | None = None):
        return None

    def create(self, _session, created_by: int | None = None):
        return None


class _Pending2FARepo:
    def create(self, _pending: str, _user_id: int, _expires_at, created_by: int | None = None):
        return None

    def get_user_id(self, _pending: str):
        return None

    def consume(self, _pending: str):
        return None


class _Tokens:
    def make_refresh_pair(self, user_id: int, *, auto_login: bool, user_ver: int, tenant_ver: int):
        return "refresh-token", {"jti": f"r-{user_id}", "exp": datetime.now(timezone.utc)}

    @staticmethod
    def hash_token(value: str) -> str:
        return f"h:{value}"

    def make_access(self, user_id: int, *, user_ver: int, tenant_ver: int, role: str):
        return f"access-{user_id}", f"jti-{user_id}"


class _Logger:
    def login_invalid_user_attempt(self, *_args, **_kwargs):
        return None

    def login_inactive_user_attempt(self, *_args, **_kwargs):
        return None

    def login_bad_password_attempt(self, *_args, **_kwargs):
        return None

    def login_successful_login(self, *_args, **_kwargs):
        return None


class _Audit:
    def log(self, *_args, **_kwargs):
        return None


class _TwoFactorSettings:
    @staticmethod
    def is_two_factor_enabled() -> bool:
        return False


class _TwoFactorService:
    def __init__(self) -> None:
        self.sent = 0

    def create_and_send_code(self, *_args, **_kwargs):
        self.sent += 1
        return None

    @staticmethod
    def verify_code(*_args, **_kwargs) -> bool:
        return True


class _AuthenticatorRepo:
    def __init__(self, secret: str | None) -> None:
        self.secret = secret

    def get_enabled_secret(self, _user_id: int):
        return self.secret

    def upsert_pending_secret(self, *args, **kwargs):
        return None

    def get_pending_secret(self, _user_id: int):
        return None

    def enable_secret(self, *_args, **_kwargs):
        return None

    def get_by_user_id(self, _user_id: int):
        return None

    def disable(self, *_args, **_kwargs):
        return None


def _build_service(*, role: str, authenticator_secret: str | None) -> LoginService:
    user = _User(
        id=11,
        email="owner@example.com",
        password_hash=pwd_hasher.hash("secret-pass"),
        role=role,
    )
    return LoginService(
        user_repository=_UserRepo(user),
        session_repository=_SessionRepo(),
        pending_2fa_repository=_Pending2FARepo(),
        tokens=_Tokens(),
        logger=_Logger(),
        two_factor_service=_TwoFactorService(),
        audit_service=_Audit(),
        two_factor_settings=_TwoFactorSettings(),
        user_authenticator_repository=_AuthenticatorRepo(authenticator_secret),
    )


def test_owner_non_trial_requires_authenticator_even_when_global_twofactor_disabled() -> None:
    svc = _build_service(role="owner", authenticator_secret="BASE32SECRET")

    result = svc.login(
        LoginInput(
            email="owner@example.com",
            password="secret-pass",
            pending_token=None,
            two_factor_code=None,
            ip="127.0.0.1",
            ua="pytest",
            tenant=TenantAuthContext(tenant_id=1, slug="misi", correlation_id="c1", security_version=0, trial_active=False),
        )
    )

    assert isinstance(result, LoginTwoFactorRequired)
    assert result.challenge_type == "authenticator"


def test_owner_non_trial_without_authenticator_is_rejected() -> None:
    svc = _build_service(role="owner", authenticator_secret=None)

    with pytest.raises(ValueError, match="authenticator_required_setup"):
        svc.login(
            LoginInput(
                email="owner@example.com",
                password="secret-pass",
                pending_token=None,
                two_factor_code=None,
                ip="127.0.0.1",
                ua="pytest",
                tenant=TenantAuthContext(tenant_id=1, slug="misi", correlation_id="c1", security_version=0, trial_active=False),
            )
        )


def test_owner_trial_can_login_without_authenticator() -> None:
    svc = _build_service(role="owner", authenticator_secret=None)

    result = svc.login(
        LoginInput(
            email="owner@example.com",
            password="secret-pass",
            pending_token=None,
            two_factor_code=None,
            ip="127.0.0.1",
            ua="pytest",
            tenant=TenantAuthContext(tenant_id=1, slug="misi", correlation_id="c1", security_version=0, trial_active=True),
        )
    )

    assert isinstance(result, LoginSuccess)


def test_owner_trial_with_enabled_authenticator_still_requires_code() -> None:
    svc = _build_service(role="owner", authenticator_secret="BASE32SECRET")

    result = svc.login(
        LoginInput(
            email="owner@example.com",
            password="secret-pass",
            pending_token=None,
            two_factor_code=None,
            ip="127.0.0.1",
            ua="pytest",
            tenant=TenantAuthContext(tenant_id=1, slug="misi", correlation_id="c1", security_version=0, trial_active=True),
        )
    )

    assert isinstance(result, LoginTwoFactorRequired)
    assert result.challenge_type == "authenticator"
