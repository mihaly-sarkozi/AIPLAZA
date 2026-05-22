from __future__ import annotations

import copy
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone

import pytest
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.modules.auth.domain.dto import LoginInput
from core.modules.auth.use_cases.login_service import LoginService
from core.modules.users.service.user_service import UserService
from core.modules.users.domain.dto.user import User


pytestmark = pytest.mark.unit


class _SnapshotTransaction(AbstractContextManager):
    def __init__(self, *targets):
        self._targets = targets
        self._snapshots = {}

    def __enter__(self):
        self._snapshots = {id(target): copy.deepcopy(target.__dict__) for target in self._targets}
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            for target in self._targets:
                target.__dict__.clear()
                target.__dict__.update(copy.deepcopy(self._snapshots[id(target)]))
        return False


class _UserRepoState:
    def __init__(self, existing: User | None = None):
        self.users_by_id = {}
        self.users_by_email = {}
        self.next_id = 1
        self.reset_failed_login_calls: list[int] = []
        self.failed_login_calls: list[int] = []
        self.security_version_bumps: list[int] = []
        if existing is not None:
            self.users_by_id[existing.id] = existing
            self.users_by_email[existing.email] = existing
            self.next_id = max(self.next_id, (existing.id or 0) + 1)

    def get_by_email(self, email: str):
        return self.users_by_email.get(email)

    def get_by_id(self, user_id: int):
        return self.users_by_id.get(user_id)

    def exists_owner(self) -> bool:
        return any(user.role == "owner" for user in self.users_by_id.values())

    def create(self, user: User, *, created_by=None) -> User:
        persisted = user.persisted(id=self.next_id, created_at=user.created_at)
        self.next_id += 1
        self.users_by_id[persisted.id] = persisted
        self.users_by_email[persisted.email] = persisted
        return persisted

    def update(self, user: User, *, updated_by=None) -> User:
        self.users_by_id[user.id] = user
        self.users_by_email[user.email] = user
        return user

    def delete(self, user_id: int, *, updated_by=None) -> None:
        user = self.users_by_id.pop(user_id)
        self.users_by_email.pop(user.email, None)

    def increment_security_version(self, user_id: int, *, updated_by=None) -> None:
        self.security_version_bumps.append(user_id)

    def record_failed_login(self, user_id: int, *, updated_by=None) -> None:
        self.failed_login_calls.append(user_id)

    def reset_failed_login(self, user_id: int, *, updated_by=None) -> None:
        self.reset_failed_login_calls.append(user_id)


class _InviteTokenRepoState:
    def __init__(self):
        self.tokens: list[tuple[int, str]] = []

    def create(self, user_id: int, token_hash: str, expires_at, *, created_by=None, updated_by=None) -> None:
        self.tokens.append((user_id, token_hash))


class _SessionRepoState:
    def __init__(self):
        self.invalidated_for_user: list[int] = []
        self.created_sessions: list[object] = []

    def invalidate_all_for_user(self, user_id: int, *, updated_by=None) -> None:
        self.invalidated_for_user.append(user_id)

    def create(self, session, *, created_by=None) -> object:
        self.created_sessions.append(session)
        return session


class _PendingRepoState:
    def create(self, pending: str, user_id: int, expires_at, *, created_by=None) -> None:
        return None

    def get_user_id(self, pending_token: str):
        return None

    def consume(self, pending_token: str) -> None:
        return None


class _NoopLogger:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _SettingsNo2FA:
    def is_two_factor_enabled(self) -> bool:
        return False


class _TwoFactorNoop:
    def create_and_send_code(self, user_id: int, email: str, pending_token: str) -> None:
        return None

    def verify_code(self, user_id: int, two_factor_code: str, pending_token: str | None = None, ip: str | None = None) -> bool:
        return True


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


class _ExplodingAudit:
    def log(self, entry, **kwargs):
        raise RuntimeError("audit append failed")


def test_user_create_rolls_back_when_audit_write_fails():
    user_repo = _UserRepoState()
    invite_repo = _InviteTokenRepoState()

    svc = UserService(
        user_repository=user_repo,
        audit_service=_ExplodingAudit(),
        invite_token_repository=invite_repo,
        email_service=None,
        transaction_manager=lambda: _SnapshotTransaction(user_repo, invite_repo),
    )

    with pytest.raises(RuntimeError, match="audit append failed"):
        svc.create(email="rollback@example.com", name="Rollback", role="user")

    assert user_repo.users_by_email == {}
    assert invite_repo.tokens == []


def test_login_success_rolls_back_session_creation_when_audit_write_fails():
    user = User(
        id=21,
        email="login@example.com",
        password_hash=pwd_hasher.hash("secret"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    user_repo = _UserRepoState(existing=user)
    session_repo = _SessionRepoState()

    svc = LoginService(
        user_repository=user_repo,
        session_repository=session_repo,
        pending_2fa_repository=_PendingRepoState(),
        tokens=_Tokens(),
        logger=_NoopLogger(),
        two_factor_service=_TwoFactorNoop(),
        audit_service=_ExplodingAudit(),
        two_factor_settings=_SettingsNo2FA(),
        transaction_manager=lambda: _SnapshotTransaction(user_repo, session_repo),
    )

    with pytest.raises(RuntimeError, match="audit append failed"):
        svc.login(
            LoginInput(
                email="login@example.com",
                password="secret",
                pending_token=None,
                two_factor_code=None,
                ip="127.0.0.1",
                ua="pytest",
            )
        )

    assert session_repo.created_sessions == []
    assert session_repo.invalidated_for_user == []
    assert user_repo.reset_failed_login_calls == []
