from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.capabilities.users.dto import InviteToken, User
from core.capabilities.users.service import InviteService, UserService
from core.capabilities.users.service.invite_errors import InviteTokenInvalidError


pytestmark = pytest.mark.unit


class _UserRepo:
    def __init__(self, *, existing: User | None = None, owner_exists: bool = False) -> None:
        self.owner_exists = owner_exists
        self.by_id: dict[int, User] = {}
        self.by_email: dict[str, User] = {}
        self.next_id = 1
        self.updated_passwords: list[tuple[int, str, int | None]] = []
        self.reset_failed_login_calls: list[tuple[int, int | None]] = []
        self.security_version_bumps: list[int] = []
        if existing is not None:
            self.by_id[existing.id] = existing
            self.by_email[existing.email] = existing
            self.next_id = (existing.id or 0) + 1

    def list_all(self):
        return list(self.by_id.values())

    def get_by_id(self, user_id: int):
        return self.by_id.get(user_id)

    def get_by_email(self, email: str):
        return self.by_email.get(email)

    def exists_owner(self) -> bool:
        return self.owner_exists or any(user.role == "owner" for user in self.by_id.values())

    def create(self, user: User, *, created_by=None) -> User:
        persisted = user.persisted(id=self.next_id, created_at=user.created_at)
        self.by_id[persisted.id] = persisted
        self.by_email[persisted.email] = persisted
        self.next_id += 1
        return persisted

    def update(self, user: User, *, updated_by=None) -> User:
        self.by_id[user.id] = user
        self.by_email[user.email] = user
        return user

    def update_password(self, user_id: int, password_hash: str, *, updated_by=None) -> None:
        self.updated_passwords.append((user_id, password_hash, updated_by))

    def reset_failed_login(self, user_id: int, *, updated_by=None) -> None:
        self.reset_failed_login_calls.append((user_id, updated_by))

    def increment_security_version(self, user_id: int, *, updated_by=None) -> None:
        self.security_version_bumps.append(user_id)

    def delete(self, user_id: int, *, updated_by=None) -> None:
        user = self.by_id.pop(user_id)
        self.by_email.pop(user.email, None)


class _InviteTokenRepo:
    def __init__(self, token: InviteToken | None = None) -> None:
        self.token = token
        self.created: list[tuple[int, str, int | None, int | None]] = []
        self.invalidated_for_user: list[tuple[int, int | None]] = []
        self.marked_used: list[tuple[int, int | None]] = []

    def create(self, user_id: int, token_hash: str, expires_at, *, created_by=None, updated_by=None) -> int:
        self.created.append((user_id, token_hash, created_by, updated_by))
        return len(self.created)

    def get_by_token_hash(self, token_hash: str):
        return self.token

    def mark_used(self, token_id: int, *, updated_by=None) -> None:
        self.marked_used.append((token_id, updated_by))

    def invalidate_all_for_user(self, user_id: int, *, updated_by=None) -> None:
        self.invalidated_for_user.append((user_id, updated_by))


class _SessionRepo:
    def __init__(self) -> None:
        self.invalidated_for_user: list[tuple[int, int | None]] = []

    def invalidate_all_for_user(self, user_id: int, *, updated_by=None) -> None:
        self.invalidated_for_user.append((user_id, updated_by))


def test_change_password_updates_hash_and_resets_failed_login():
    user = User(
        id=60,
        email="changepass@example.com",
        password_hash=pwd_hasher.hash("OldPass1"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=True,
    )
    user_repo = _UserRepo(existing=user, owner_exists=True)
    session_repo = _SessionRepo()
    svc = UserService(
        user_repository=user_repo,
        invite_token_repository=_InviteTokenRepo(),
        session_repository=session_repo,
        email_service=None,
    )

    svc.change_password(user_id=60, current_password="OldPass1", new_password="NewStrongPass1")

    assert user_repo.updated_passwords and user_repo.updated_passwords[0][0] == 60
    assert user_repo.reset_failed_login_calls == [(60, 60)]
    assert user_repo.security_version_bumps == []
    assert session_repo.invalidated_for_user == []


def test_change_password_rejects_when_credentials_password_not_set():
    user = User(
        id=61,
        email="initial-only@example.com",
        password_hash=pwd_hasher.hash("OldPass1"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=False,
    )
    svc = UserService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="credentials_password_not_set"):
        svc.change_password(user_id=61, current_password="OldPass1", new_password="NewStrongPass1")


def test_change_password_rejects_when_user_not_found():
    svc = UserService(
        user_repository=_UserRepo(owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="user_not_found"):
        svc.change_password(user_id=999, current_password="OldPass1", new_password="NewStrongPass1")


def test_change_password_rejects_wrong_current_password():
    user = User(
        id=62,
        email="wrong-current@example.com",
        password_hash=pwd_hasher.hash("CorrectPass1"),
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=True,
    )
    user_repo = _UserRepo(existing=user, owner_exists=True)
    svc = UserService(
        user_repository=user_repo,
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="current_password_wrong"):
        svc.change_password(user_id=62, current_password="WrongPass1", new_password="NewStrongPass1")

    assert user_repo.updated_passwords == []
    assert user_repo.reset_failed_login_calls == []


def test_set_password_promotes_first_completed_registration_to_owner():
    user = User(
        id=1,
        email="invite@example.com",
        password_hash="old-hash",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    invite = InviteToken(
        id=10,
        user_id=1,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=None,
    )
    user_repo = _UserRepo(existing=user, owner_exists=False)
    invite_repo = _InviteTokenRepo(invite)
    svc = InviteService(user_repository=user_repo, invite_token_repository=invite_repo, email_service=None)

    svc.set_password("valid-token", "StrongPass1")

    updated = user_repo.get_by_id(1)
    assert updated is not None
    assert updated.is_active is True
    assert updated.role == "owner"
    assert updated.registration_completed_at is not None
    assert invite_repo.marked_used == [(10, 1)]
    assert user_repo.updated_passwords and user_repo.updated_passwords[0][0] == 1


def test_set_password_used_token_raises_invalid_token():
    invite = InviteToken(
        id=11,
        user_id=2,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        used_at=datetime.now(timezone.utc),
    )
    svc = InviteService(
        user_repository=_UserRepo(),
        invite_token_repository=_InviteTokenRepo(invite),
        email_service=None,
    )

    with pytest.raises(InviteTokenInvalidError):
        svc.set_password("used-token", "StrongPass1")


def test_validate_invite_token_covers_invalid_expired_used_and_valid_states():
    now = datetime.now(timezone.utc)
    svc = InviteService(
        user_repository=_UserRepo(),
        invite_token_repository=_InviteTokenRepo(None),
        email_service=None,
    )
    assert svc.validate_invite_token("") == "invalid"

    valid_invite = InviteToken(id=1, user_id=2, expires_at=now + timedelta(minutes=10), used_at=None)
    expired_invite = InviteToken(id=2, user_id=2, expires_at=now - timedelta(minutes=1), used_at=None)
    used_invite = InviteToken(id=3, user_id=2, expires_at=now + timedelta(minutes=10), used_at=now)

    svc.invite_token_repo = _InviteTokenRepo(valid_invite)
    assert svc.validate_invite_token("valid") == "valid"

    svc.invite_token_repo = _InviteTokenRepo(expired_invite)
    assert svc.validate_invite_token("expired") == "expired"

    svc.invite_token_repo = _InviteTokenRepo(used_invite)
    assert svc.validate_invite_token("used") == "invalid"


def test_resend_invite_invalidates_previous_tokens_and_creates_new_one():
    user = User(
        id=3,
        email="pending@example.com",
        password_hash="hash",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    invite_repo = _InviteTokenRepo()
    svc = InviteService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=invite_repo,
        email_service=None,
    )

    svc.resend_invite(user_id=3, request_base_url="http://demo.local", updated_by=99)

    assert invite_repo.invalidated_for_user == [(3, 99)]
    assert len(invite_repo.created) == 1
    created_user_id, _, created_by, updated_by = invite_repo.created[0]
    assert created_user_id == 3
    assert created_by == 99
    assert updated_by == 99


def test_resend_invite_active_user_raises():
    user = User(
        id=30,
        email="active@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    svc = InviteService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="már aktív"):
        svc.resend_invite(user_id=30, request_base_url="http://demo.local", updated_by=1)


def test_forgot_password_unknown_email_is_noop():
    invite_repo = _InviteTokenRepo()
    svc = UserService(
        user_repository=_UserRepo(),
        invite_token_repository=invite_repo,
        email_service=None,
    )

    svc.forgot_password("missing@example.com", request_base_url="http://demo.local")

    assert invite_repo.invalidated_for_user == []
    assert invite_repo.created == []


def test_forgot_password_existing_user_invalidates_and_creates_new_token():
    user = User(
        id=40,
        email="known@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    invite_repo = _InviteTokenRepo()
    svc = UserService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=invite_repo,
        email_service=None,
    )

    svc.forgot_password("known@example.com", request_base_url="http://demo.local")

    assert invite_repo.invalidated_for_user == [(40, 40)]
    assert len(invite_repo.created) == 1
    created_user_id, _, created_by, updated_by = invite_repo.created[0]
    assert created_user_id == 40
    assert created_by == 40
    assert updated_by == 40


def test_set_initial_password_demo_updates_password_resets_failed_login_and_security_version():
    user = User(
        id=50,
        email="demo@example.com",
        password_hash="placeholder-hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=False,
    )
    user_repo = _UserRepo(existing=user, owner_exists=True)
    svc = UserService(
        user_repository=user_repo,
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    svc.set_initial_password_demo(user_id=50, new_password="StrongPass1", tenant_demo_mode=True)

    assert user_repo.updated_passwords and user_repo.updated_passwords[0][0] == 50
    assert user_repo.reset_failed_login_calls == [(50, 50)]
    assert user_repo.security_version_bumps == [50]


def test_set_initial_password_demo_rejects_when_credentials_already_set():
    user = User(
        id=51,
        email="already-set@example.com",
        password_hash="real-hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=True,
    )
    svc = UserService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="credentials_already_set"):
        svc.set_initial_password_demo(user_id=51, new_password="StrongPass1", tenant_demo_mode=True)


def test_set_initial_password_demo_rejects_when_tenant_is_not_demo():
    user = User(
        id=52,
        email="nondemo@example.com",
        password_hash="placeholder-hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        credentials_password_set=False,
    )
    svc = UserService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="not_demo_tenant"):
        svc.set_initial_password_demo(user_id=52, new_password="StrongPass1", tenant_demo_mode=False)


def test_update_rejects_self_role_change():
    user = User(
        id=4,
        email="self@example.com",
        password_hash="hash",
        is_active=True,
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    svc = UserService(
        user_repository=_UserRepo(existing=user, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="saját szerepköröd"):
        svc.update(user_id=4, current_user_id=4, role="user")


def test_delete_rejects_owner_target():
    owner = User(
        id=5,
        email="owner@example.com",
        password_hash="hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
    )
    svc = UserService(
        user_repository=_UserRepo(existing=owner, owner_exists=True),
        invite_token_repository=_InviteTokenRepo(),
        session_repository=_SessionRepo(),
        email_service=None,
    )

    with pytest.raises(ValueError, match="ownert nem lehet törölni"):
        svc.delete(user_id=5, current_user_id=99)
