from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.kernel.config.config_loader import settings
from admin.service.platform_admin_service import PlatformAdminService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass
class _User:
    id: int
    email: str
    password_hash: str
    is_active: bool = True
    deleted_at: object | None = None
    failed_login_attempts: int = 0
    security_version: int = 1
    role: str = "admin"
    mfa_enabled: bool = True
    mfa_secret_base32: str = "SECRET"


class _RepoStub:
    def __init__(self, user: _User) -> None:
        self.user = user
        self.invalidated = 0
        self._blocked = False

    def get_by_email(self, _email: str):
        return self.user

    def update_user(self, _user_id: int, **kwargs):
        if "failed_login_attempts" in kwargs and kwargs["failed_login_attempts"] is not None:
            self.user.failed_login_attempts = int(kwargs["failed_login_attempts"])
        return self.user

    def consume_mfa_recovery_code(self, _user_id: int, *, code_hash: str, updated_by: int | None = None) -> bool:
        return False

    def is_platform_admin_mfa_scope_blocked(self, *, scope: str, scope_key: str) -> bool:
        return self._blocked

    def record_platform_admin_mfa_failed_attempt(
        self,
        *,
        scope: str,
        scope_key: str,
        max_attempts: int,
        window_minutes: int,
        lock_minutes: int,
        actor_user_id: int | None = None,
    ) -> bool:
        self._blocked = True
        return True

    def reset_platform_admin_mfa_attempts(self, *, scopes, actor_user_id: int | None = None) -> None:
        self._blocked = False

    def invalidate_all_refresh_sessions_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        self.invalidated += 1


class _TokenServiceStub:
    def make_platform_admin_access(self, user_id: int, *, user_ver: int, role: str):
        return "access", "jti-1"

    def make_platform_admin_refresh_pair(self, user_id: int, *, user_ver: int):
        return "refresh", {"jti": "r1", "exp": datetime.now(timezone.utc)}

    @staticmethod
    def hash_token(value: str) -> str:
        return f"h:{value}"


class _EmailStub:
    def __init__(self) -> None:
        self.sent = []

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        self.sent.append((to_email, subject, body))
        return True


def test_platform_admin_mfa_lockout_invalidates_sessions_and_sends_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _User(
        id=7,
        email="admin@example.com",
        password_hash=pwd_hasher.hash("correct-password"),
    )
    repo = _RepoStub(user)
    email = _EmailStub()
    svc = PlatformAdminService(repository=repo, token_service=_TokenServiceStub(), email_service=email)

    monkeypatch.setattr(settings, "platform_admin_login_alert_email", "ops@example.com", raising=False)
    monkeypatch.setattr("admin.service.platform_admin_service.allowlist_remove_by_user", lambda tenant, uid: None)
    monkeypatch.setattr("admin.service.platform_admin_service.LoginService.verify_authenticator_code", lambda secret, code: False)

    with pytest.raises(ValueError, match="platform_admin_mfa_locked"):
        svc.login(
            "admin@example.com",
            "correct-password",
            ip="1.2.3.4",
            ua="pytest-agent",
            mfa_code="123456",
        )

    assert repo.invalidated == 1
    assert len(email.sent) == 1
