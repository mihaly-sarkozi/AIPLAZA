from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import jwt
import pytest
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.auth.domain.dto import LoginInput, LoginTwoFactorRequired
from core.modules.auth.domain.exceptions import TwoFactorTooManyAttemptsError
from core.modules.auth.use_cases.login_service import LoginService
from core.modules.auth.use_cases.logout_service import LogoutService
from core.modules.auth.use_cases.refresh_service import RefreshService
from core.modules.auth.domain.dto.session import Session
from core.modules.users.service.user_service import UserService
from core.modules.users.domain.dto.user import User


pytestmark = pytest.mark.unit


class _NoopLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _UserRepo:
    def __init__(self, user: User | None = None) -> None:
        self.user = user

    def get_by_email(self, email: str):
        if self.user and self.user.email == email:
            return self.user
        return None

    def get_by_id(self, user_id: int):
        if self.user and self.user.id == user_id:
            return self.user
        return None

    def record_failed_login(self, user_id: int, *, updated_by=None) -> None:
        return None

    def reset_failed_login(self, user_id: int, *, updated_by=None) -> None:
        return None

    def create(self, user: User, *, created_by=None) -> User:
        return user.persisted(id=42, created_at=user.created_at)

    def exists_owner(self) -> bool:
        return True

    def list_all(self):
        return []

    def update(self, user: User, *, updated_by=None) -> User:
        return user

    def increment_security_version(self, user_id: int, *, updated_by=None) -> None:
        return None

    def delete(self, user_id: int, *, updated_by=None) -> None:
        return None


class _SessionRepo:
    def __init__(self, session: Session | None = None) -> None:
        self.session = session
        self.invalidated_all_for_user: list[int] = []
        self.created: list[Session] = []
        self.updated: list[Session] = []

    def invalidate_all_for_user(self, user_id: int, *, updated_by=None) -> None:
        self.invalidated_all_for_user.append(user_id)

    def create(self, session: Session, *, created_by=None) -> Session:
        self.created.append(session)
        return session

    def get_by_jti(self, jti: str):
        if self.session and self.session.jti == jti:
            return self.session
        return None

    def update(self, session: Session, *, updated_by=None) -> Session:
        self.updated.append(session)
        self.session = session
        return session


class _PendingRepo:
    def __init__(self, user_id: int | None = None) -> None:
        self.user_id = user_id
        self.created: list[tuple[str, int]] = []
        self.consumed: list[str] = []

    def create(self, pending: str, user_id: int, expires_at, *, created_by=None) -> None:
        self.created.append((pending, user_id))
        self.user_id = user_id

    def get_user_id(self, pending_token: str):
        return self.user_id

    def consume(self, pending_token: str) -> None:
        self.consumed.append(pending_token)


class _TwoFactorService:
    def __init__(self, verify_result=True) -> None:
        self.verify_result = verify_result
        self.sent_codes: list[tuple[int, str, str]] = []

    def create_and_send_code(self, user_id: int, email: str, pending_token: str) -> None:
        self.sent_codes.append((user_id, email, pending_token))

    def verify_code(self, user_id: int, two_factor_code: str, pending_token: str | None = None, ip: str | None = None) -> bool:
        return self.verify_result


class _Tokens:
    def make_refresh_pair(self, user_id: int, auto_login: bool = False, user_ver: int = 0, tenant_ver: int = 0):
        return (
            "refresh-token",
            {
                "jti": "refresh-jti",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            },
        )

    def hash_token(self, token: str) -> str:
        return f"hashed:{token}"

    def make_access(self, user_id: int, user_ver: int = 0, tenant_ver: int = 0, role: str = "user"):
        return ("access-token", "access-jti")

    def verify(self, token: str):
        raise NotImplementedError

    def decode_ignore_exp(self, token: str):
        return None


class _Settings2FAEnabled:
    def is_two_factor_enabled(self) -> bool:
        return True


def _audit_action(mock: MagicMock):
    assert mock.log.call_args is not None
    return mock.log.call_args.args[0]


def _audit_reason(mock: MagicMock):
    assert mock.log.call_args is not None
    return mock.log.call_args.kwargs["details"]["reason"]


def test_login_invalid_user_writes_login_failed_audit():
    audit = MagicMock()
    svc = LoginService(
        user_repository=_UserRepo(None),
        session_repository=_SessionRepo(),
        pending_2fa_repository=_PendingRepo(),
        tokens=_Tokens(),
        logger=_NoopLogger(),
        two_factor_service=_TwoFactorService(),
        audit_service=audit,
        two_factor_settings=_Settings2FAEnabled(),
    )

    result = svc.login(LoginInput(email="missing@example.com", password="secret", pending_token=None, two_factor_code=None, ip="127.0.0.1", ua="pytest"))

    assert result is None
    assert _audit_action(audit) == AuditLogAction.LOGIN_FAILED
    assert _audit_reason(audit) == "invalid_user"


def test_login_step1_success_writes_login_2fa_required_audit():
    user = User(
        id=5,
        email="user@example.com",
        password_hash=pwd_hasher.hash("secret"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    audit = MagicMock()
    two_factor = _TwoFactorService()
    svc = LoginService(
        user_repository=_UserRepo(user),
        session_repository=_SessionRepo(),
        pending_2fa_repository=_PendingRepo(),
        tokens=_Tokens(),
        logger=_NoopLogger(),
        two_factor_service=two_factor,
        audit_service=audit,
        two_factor_settings=_Settings2FAEnabled(),
    )

    result = svc.login(LoginInput(email="user@example.com", password="secret", pending_token=None, two_factor_code=None, ip="127.0.0.1", ua="pytest"))

    assert isinstance(result, LoginTwoFactorRequired)
    assert _audit_action(audit) == AuditLogAction.LOGIN_2FA_REQUIRED


def test_login_step2_invalid_code_writes_login_2fa_failed_audit():
    user = User(
        id=7,
        email="user@example.com",
        password_hash=pwd_hasher.hash("secret"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    audit = MagicMock()
    svc = LoginService(
        user_repository=_UserRepo(user),
        session_repository=_SessionRepo(),
        pending_2fa_repository=_PendingRepo(user_id=7),
        tokens=_Tokens(),
        logger=_NoopLogger(),
        two_factor_service=_TwoFactorService(verify_result=False),
        audit_service=audit,
        two_factor_settings=_Settings2FAEnabled(),
    )

    result = svc.login(LoginInput(email=None, password=None, pending_token="pending-1", two_factor_code="123456", ip="127.0.0.1", ua="pytest"))

    assert result is None
    assert _audit_action(audit) == AuditLogAction.LOGIN_2FA_FAILED
    assert _audit_reason(audit) == "invalid_code"


def test_login_step2_authenticator_invalid_code_rate_limited_and_consumes_pending():
    class _AttemptRepo:
        def __init__(self) -> None:
            self.counts: dict[tuple[str, str], int] = {}

        def is_blocked(self, scope: str, scope_key: str, max_attempts: int, window_minutes: int) -> bool:
            return int(self.counts.get((scope, scope_key), 0)) >= int(max_attempts)

        def record_failed(self, scope: str, scope_key: str, window_minutes: int, *, actor_user_id: int) -> int:
            key = (scope, scope_key)
            next_count = int(self.counts.get(key, 0)) + 1
            self.counts[key] = next_count
            return next_count

        def reset_for_success(self, pending_token_key: str, user_id: int, ip: str | None, *, actor_user_id: int) -> None:
            return None

    class _AuthenticatorRepo:
        def get_enabled_secret(self, user_id: int):
            return "JBSWY3DPEHPK3PXP"

    user = User(
        id=11,
        email="totp@example.com",
        password_hash=pwd_hasher.hash("secret"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    audit = MagicMock()
    pending = _PendingRepo(user_id=11)
    two_factor = _TwoFactorService(verify_result=False)
    two_factor.attempt_repo = _AttemptRepo()
    two_factor.max_attempts = 5
    two_factor.attempt_window_minutes = 15
    svc = LoginService(
        user_repository=_UserRepo(user),
        session_repository=_SessionRepo(),
        pending_2fa_repository=pending,
        tokens=_Tokens(),
        logger=_NoopLogger(),
        two_factor_service=two_factor,
        audit_service=audit,
        two_factor_settings=_Settings2FAEnabled(),
        user_authenticator_repository=_AuthenticatorRepo(),
    )

    for _ in range(4):
        result = svc.login(
            LoginInput(
                email=None,
                password=None,
                pending_token="pending-totp",
                two_factor_code="000000",
                ip="127.0.0.1",
                ua="pytest",
            )
        )
        assert result is None
    with pytest.raises(TwoFactorTooManyAttemptsError):
        svc.login(
            LoginInput(
                email=None,
                password=None,
                pending_token="pending-totp",
                two_factor_code="000000",
                ip="127.0.0.1",
                ua="pytest",
            )
        )
    assert pending.consumed[-1] == "pending-totp"
    assert _audit_action(audit) == AuditLogAction.LOGIN_2FA_RATE_LIMITED
    assert _audit_reason(audit) == "too_many_attempts"


def test_refresh_invalid_token_writes_refresh_failed_audit():
    class _InvalidRefreshTokens(_Tokens):
        def verify(self, token: str):
            raise jwt.DecodeError("bad token")

    audit = MagicMock()
    svc = RefreshService(
        session_repository=_SessionRepo(),
        tokens=_InvalidRefreshTokens(),
        logger=_NoopLogger(),
        audit_service=audit,
    )

    result = svc.refresh("bad-token", ip="127.0.0.1", ua="pytest")

    from core.modules.auth.use_cases.refresh_result import RefreshFailed, RefreshFailReason

    assert isinstance(result, RefreshFailed)
    assert result.reason == RefreshFailReason.INVALID_TOKEN
    assert _audit_action(audit) == AuditLogAction.REFRESH_FAILED
    assert _audit_reason(audit) == "invalid_token"


def test_logout_success_writes_logout_audit():
    session = Session.new(
        user_id=9,
        jti="refresh-jti",
        token_hash="hashed:refresh-token",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ip="127.0.0.1",
        user_agent="pytest",
    )

    class _LogoutTokens(_Tokens):
        def verify(self, token: str):
            return {"typ": "refresh", "sub": "9", "jti": "refresh-jti"}

    audit = MagicMock()
    svc = LogoutService(
        session_repository=_SessionRepo(session),
        tokens=_LogoutTokens(),
        logger=_NoopLogger(),
        audit_service=audit,
    )

    result = svc.logout("refresh-token", ip="127.0.0.1", ua="pytest")

    assert result is True
    assert _audit_action(audit) == AuditLogAction.LOGOUT


def test_user_service_emits_expected_audit_actions_for_create_update_and_delete():
    user = User(
        id=11,
        email="before@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        name="Before",
    )
    user_repo = _UserRepo(user)
    user_repo.get_by_id = lambda user_id: user
    user_repo.get_by_email = lambda email: None if email != user.email else user
    invite_repo = SimpleNamespace(create=lambda *args, **kwargs: None)
    audit = MagicMock()
    svc = UserService(
        user_repository=user_repo,
        audit_service=audit,
        invite_token_repository=invite_repo,
        email_service=None,
    )

    created = svc.create(email="new@example.com", name="New User", role="user")
    updated = svc.update(
        user_id=11,
        current_user_id=99,
        name="After",
        is_active=False,
        email="after@example.com",
        role="admin",
    )
    svc.delete(user_id=11, current_user_id=99)

    actions = [call.args[0] for call in audit.log.call_args_list]
    assert created.email == "new@example.com"
    assert updated.email == "after@example.com"
    assert actions == [
        AuditLogAction.USER_CREATED,
        AuditLogAction.USER_EMAIL_CHANGED,
        AuditLogAction.USER_ROLE_CHANGED,
        AuditLogAction.USER_UPDATED,
        AuditLogAction.USER_DELETED,
    ]
