# apps/users/application/services/user_service.py
# User kezelési szolgáltatás. Létrehozáskor nincs jelszó: emailben megy a link, 24h alatt a user állítja be.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from passlib.hash import bcrypt_sha256 as pwd_hasher

from config.settings import settings
from apps.core.validation import is_valid_email
from apps.users.ports import UserRepositoryInterface, InviteTokenRepositoryInterface

def _invite_ttl_hours() -> int:
    """Invite/set-password token TTL (óra); 1–4 óra ajánlott, max 24."""
    return max(1, min(24, getattr(settings, "invite_ttl_hours", 4)))
from apps.users.domain.user import User
from apps.audit.application.audit_service import AuditService


class UserService:
    def __init__(
        self,
        user_repository: UserRepositoryInterface,
        audit_service: Optional[AuditService] = None,
        invite_token_repository: Optional[InviteTokenRepositoryInterface] = None,
        email_service=None,
    ):
        self.user_repository = user_repository
        self.audit = audit_service
        self.invite_token_repo = invite_token_repository
        self.email_service = email_service

    def list_all(self) -> list[User]:
        """Minden user listázása."""
        return self.user_repository.list_all()

    def get_user_ids_with_used_token(self) -> set[int]:
        """Azon user_id-k, akik már egyszer regisztráltak (használtak meghívó linket)."""
        return self.invite_token_repo.get_user_ids_with_used_token() if self.invite_token_repo else set()

    def get_by_id(self, user_id: int) -> User | None:
        """User lekérdezése azonosító alapján."""
        return self.user_repository.get_by_id(user_id)

    def create(
        self,
        email: str,
        name: str | None = None,
        role: str = "user",
        request_base_url: str | None = None,
    ) -> User:
        """User létrehozása jelszó nélkül (is_active=False); emailben megy a invite_ttl_hours érvényes regisztrációs link. Owner csak az első regisztráló lehet."""
        if not is_valid_email(email):
            raise ValueError("Érvénytelen email cím.")
        email = (email or "").strip()
        if self.user_repository.get_by_email(email):
            raise ValueError("Email already exists")
        if role not in ["user", "admin"]:
            raise ValueError("Invalid role. Must be 'user' or 'admin'")
        placeholder_password = secrets.token_urlsafe(32)
        password_hash = pwd_hasher.hash(placeholder_password)
        user = User.new(
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=False,
            name=name or None,
        )
        created = self.user_repository.create(user)
        if not created.id:
            raise ValueError("Failed to create user")

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=_invite_ttl_hours())
        self.invite_token_repo.create(created.id, token_hash, expires_at)

        set_password_link = self._build_set_password_link(request_base_url, token)
        if set_password_link and self.email_service:
            self.email_service.send_set_password_invite(email, set_password_link)

        if self.audit:
            self.audit.log("user_created", user_id=created.id, details={"email": email, "role": role})
        return created

    def validate_invite_token(self, token: str) -> str:
        """Vissza: 'valid' | 'expired' | 'invalid'. 'invalid' = nincs ilyen token vagy már felhasználták (pl. új linket küldtek)."""
        if not token or not self.invite_token_repo:
            return "invalid"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = self.invite_token_repo.get_by_token_hash(token_hash)
        if not record:
            return "invalid"
        if record.used_at:
            return "invalid"
        now = datetime.now(timezone.utc)
        if record.expires_at < now:
            return "expired"
        return "valid"

    def set_password(self, token: str, password: str) -> None:
        """
        Token + jelszó beállítása (meghívott user). Jelszó erősség a request validátorban.
        Sikeres regisztráció után a user is_active=True lesz.
        Raises ValueError("token_expired") vagy ValueError("invalid_token").
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = self.invite_token_repo.get_by_token_hash(token_hash) if self.invite_token_repo else None
        if not record:
            raise ValueError("invalid_token")
        if record.used_at:
            raise ValueError("invalid_token")
        now = datetime.now(timezone.utc)
        if record.expires_at < now:
            raise ValueError("token_expired")
        self.user_repository.update_password(record.user_id, pwd_hasher.hash(password))
        self.invite_token_repo.mark_used(record.id)
        user = self.user_repository.get_by_id(record.user_id)
        if user:
            updates = {
                "is_active": True,
                "registration_completed_at": datetime.now(timezone.utc),
                "failed_login_attempts": 0,
            }
            if not self.user_repository.exists_owner():
                updates["role"] = "owner"
            self.user_repository.update(user.with_updates(**updates))
        if self.audit:
            self.audit.log("password_set_by_invite", user_id=record.user_id, details={})

    def update(
        self,
        user_id: int,
        current_user_id: int,
        name: str | None = None,
        is_active: bool | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> User:
        """User módosítása. Owner célpont: csak az owner szerkesztheti (csak név). User/admin: név, is_active, email, role – de a saját szerepköröd nem módosítható. Email/szerepkör változás audit log."""
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_owner:
            if current_user_id != user_id:
                raise ValueError("Az owner adatait csak az owner szerkesztheti.")
            if is_active is not None or email is not None or role is not None:
                raise ValueError("Owner esetén csak a név módosítható.")
            updates = {"name": name} if name is not None else {}
        else:
            updates = {}
            if name is not None:
                updates["name"] = name
            if is_active is not None:
                updates["is_active"] = is_active
            if email is not None:
                email = email.strip()
                if not is_valid_email(email):
                    raise ValueError("Érvénytelen email cím.")
                existing = self.user_repository.get_by_email(email)
                if existing and existing.id != user_id:
                    raise ValueError("Ez az email már használatban van.")
                updates["email"] = email
            if role is not None:
                if user_id == current_user_id:
                    raise ValueError("A saját szerepköröd nem módosítható.")
                if role not in ("user", "admin"):
                    raise ValueError("Szerepkör csak 'user' vagy 'admin' lehet.")
                updates["role"] = role
        if not updates:
            return user
        updated_user = user.with_updates(**updates)
        result = self.user_repository.update(updated_user)
        if self.audit and result.id:
            if email is not None and user.email != email:
                self.audit.log(
                    "user_email_changed",
                    user_id=result.id,
                    details={
                        "old_value": user.email,
                        "new_value": email,
                        "changed_by": current_user_id,
                    },
                )
            if role is not None and user.role != role:
                self.audit.log(
                    "user_role_changed",
                    user_id=result.id,
                    details={
                        "old_value": user.role,
                        "new_value": role,
                        "changed_by": current_user_id,
                    },
                )
            other = {k: v for k, v in updates.items() if k in ("name", "is_active")}
            if other:
                self.audit.log("user_updated", user_id=result.id, details={**other, "changed_by": current_user_id})
        return result

    def increment_security_version(self, user_id: int) -> None:
        """User-oldali force revoke: role/jogosultság változás után minden régi token (user_ver) bukik."""
        self.user_repository.increment_security_version(user_id)

    def delete(self, user_id: int, current_user_id: int) -> None:
        """User törlése. Az owner nem törölhető."""
        if user_id == current_user_id:
            raise ValueError("Saját magad nem törölheted.")
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_owner:
            raise ValueError("Az ownert nem lehet törölni.")
        if self.audit:
            self.audit.log("user_deleted", user_id=user_id, details={"email": user.email})
        self.user_repository.delete(user_id)

    def _build_set_password_link(self, request_base_url: str | None, token: str) -> str:
        """Link: request scheme+host + config path + ?token=..."""
        base = (request_base_url or "").strip().rstrip("/")
        path = (settings.frontend_set_password_path or "/set-password").strip()
        if path and not path.startswith("/"):
            path = "/" + path
        if not base:
            return ""
        return f"{base}{path}?token={token}"

    def resend_invite(self, user_id: int, request_base_url: str | None = None) -> None:
        """Regisztrációs link újraküldése. A korábbi link(ek) érvénytelenítve; csak az utolsó link él."""
        user = self.user_repository.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_active:
            raise ValueError("A felhasználó már aktív. Csak inaktív (zárolt vagy megerősítésre váró) usereknek küldhető link.")
        if user.is_owner:
            raise ValueError("Az owner már aktív.")
        self.invite_token_repo.invalidate_all_for_user(user_id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=_invite_ttl_hours())
        self.invite_token_repo.create(user_id, token_hash, expires_at)
        set_password_link = self._build_set_password_link(request_base_url, token)
        if set_password_link and self.email_service:
            self.email_service.send_set_password_invite(user.email, set_password_link)
        if self.audit:
            self.audit.log("invite_resent", user_id=user_id, details={"email": user.email})

    def forgot_password(self, email: str, request_base_url: str | None = None) -> None:
        """
        Elfelejtett jelszó: ha az email szerepel az adatbázisban, érvénytelenítjük a régi tokeneket,
        új set-password linket küldünk. Ha nincs ilyen user, nem dobunk hibát (ne lehessen kideríteni).
        """
        if not is_valid_email(email):
            return
        user = self.user_repository.get_by_email((email or "").strip())
        if not user or not self.invite_token_repo:
            return
        self.invite_token_repo.invalidate_all_for_user(user.id)
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=_invite_ttl_hours())
        self.invite_token_repo.create(user.id, token_hash, expires_at)
        set_password_link = self._build_set_password_link(request_base_url, token)
        if set_password_link and self.email_service:
            self.email_service.send_set_password_invite(user.email, set_password_link)
        if self.audit:
            self.audit.log("forgot_password_link_sent", user_id=user.id, details={"email": user.email})
