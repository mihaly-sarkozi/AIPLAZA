# Felhasználó modul üzleti logikája.
# 2026.04.03 - Sárközi Mihály

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.capabilities.auth.repositories.session_repository import SessionRepository
from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.email.email_service import EmailService
from core.capabilities.users.dto.user import User
from core.capabilities.users.ports import (
    InviteTokenRepositoryPort,
    SessionRepositoryPort,
    UserEmailPort,
    UserRepositoryPort,
)
from core.kernel.db.transactional_service import TransactionalService
from core.platform.auth.password_policy import validate_password_policy
from core.capabilities.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload


class UserService(TransactionalService):
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        *,
        user_repository: UserRepositoryPort,
        invite_token_repository: InviteTokenRepositoryPort | None = None,
        audit_service: AuditService | None = None,
        session_repository: SessionRepositoryPort | None = None,
        email_service: UserEmailPort | EmailService | None = None,
        transaction_manager=None,
    ) -> None:
        super().__init__(transaction_manager=transaction_manager)
        self.user_repository = user_repository
        self.audit = audit_service
        self.invite_token_repo = invite_token_repository
        self.session_repository = session_repository
        self.email_service = email_service

    # Ez a metódus listázza a(z) all logikáját.
    def list_all(self) -> list[User]:
        return self.user_repository.list_all()

    # Ez a metódus visszaadja a(z) by id logikáját.
    def get_by_id(self, user_id: int) -> User | None:
        return self.user_repository.get_by_id(user_id)

    # Jelszó módosítása aktuális jelszó ellenőrzésével
    def change_password(self, *, user_id: int, current_password: str, new_password: str) -> None:
        with self._transaction():
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise ValueError("user_not_found")
            if not getattr(user, "credentials_password_set", True):
                raise ValueError("credentials_password_not_set")
            if not pwd_hasher.verify(current_password, user.password_hash):
                raise ValueError("current_password_wrong")
            new_hash = pwd_hasher.hash(new_password)
            self.user_repository.update_password(user_id, new_hash, updated_by=user_id)
            self.user_repository.reset_failed_login(user_id, updated_by=user_id)

    def set_initial_password_demo(self, *, user_id: int, new_password: str, tenant_demo_mode: bool) -> None:
        if not tenant_demo_mode:
            raise ValueError("not_demo_tenant")
        ok, msg = validate_password_policy(new_password)
        if not ok:
            raise ValueError(msg or "invalid_password")
        with self._transaction():
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise ValueError("user_not_found")
            if getattr(user, "credentials_password_set", True):
                raise ValueError("credentials_already_set")
            self.user_repository.update_password(user_id, pwd_hasher.hash(new_password), updated_by=user_id)
            self.user_repository.reset_failed_login(user_id, updated_by=user_id)
            self.user_repository.increment_security_version(user_id, updated_by=user_id)


    # Felhasználó létrehozása
    def create(
        self,
        email: str,
        name: str | None = None,
        role: str = "user",
        request_base_url: str | None = None,
        created_by: int | None = None,
        *,
        send_invite_email: bool = True,
        activate_immediately: bool = False,
    ) -> User:
        if self.invite_token_repo is None:
            raise RuntimeError("InviteTokenRepository is not configured")

        with self._transaction():
            email = email.strip()
            if self.user_repository.get_by_email(email):
                raise ValueError("Email already exists")
            if role == "owner":
                if self.user_repository.exists_owner():
                    raise ValueError("Invalid role. Owner already exists")
            elif role not in ["user", "admin"]:
                raise ValueError("Invalid role. Must be 'user', 'admin' or 'owner' (owner only if none yet)")

            placeholder_password = secrets.token_urlsafe(32)
            password_hash = pwd_hasher.hash(placeholder_password)
            from core.kernel.clock import utc_now

            registration_completed_at = utc_now() if activate_immediately else None
            user = User.new(
                email=email,
                password_hash=password_hash,
                role=role,
                is_active=activate_immediately,
                name=name or None,
            ).with_updates(registration_completed_at=registration_completed_at)
            created = self.user_repository.create(user, created_by=created_by)
            if not created.id:
                raise ValueError("Failed to create user")

            if not activate_immediately:
                invite_payload = new_invite_token_payload()
                self.invite_token_repo.create(
                    created.id,
                    invite_payload.token_hash,
                    invite_payload.expires_at,
                    created_by=created_by,
                    updated_by=created_by,
                )

                set_password_link = build_set_password_link(request_base_url, invite_payload.raw_token)
                if send_invite_email and set_password_link and self.email_service:
                    self.email_service.send_set_password_invite(email, set_password_link)

            if self.audit:
                self.audit.log(
                    AuditLogAction.USER_CREATED,
                    user_id=created.id,
                    details={"email": email, "role": role},
                )
            return created

    # Felhasználó adatainak módosítása
    def update(
        self,
        user_id: int,
        current_user_id: int,
        name: str | None = None,
        is_active: bool | None = None,
        email: str | None = None,
        role: str | None = None,
    ) -> User:
        with self._transaction():
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
                    existing = self.user_repository.get_by_email(email)
                    if existing and existing.id != user_id:
                        raise ValueError("Ez az email már használatban van.")
                    updates["email"] = email
                if role is not None:
                    if user_id == current_user_id:
                        raise ValueError("A saját szerepköröd nem módosítható.")
                    updates["role"] = role

            if not updates:
                return user

            result = self.user_repository.update(user.with_updates(**updates), updated_by=current_user_id)
            auth_state_changed = (
                (role is not None and user.role != role)
                or (is_active is not None and user.is_active != is_active)
            )
            if auth_state_changed:
                if self.session_repository is not None:
                    self.session_repository.invalidate_all_for_user(result.id, updated_by=current_user_id)
                self.user_repository.increment_security_version(result.id, updated_by=current_user_id)

            if self.audit and result.id:
                if email is not None and user.email != email:
                    self.audit.log(
                        AuditLogAction.USER_EMAIL_CHANGED,
                        user_id=result.id,
                        details={
                            "old_value": user.email,
                            "new_value": email,
                            "changed_by": current_user_id,
                        },
                    )
                if role is not None and user.role != role:
                    self.audit.log(
                        AuditLogAction.USER_ROLE_CHANGED,
                        user_id=result.id,
                        details={
                            "old_value": user.role,
                            "new_value": role,
                            "changed_by": current_user_id,
                        },
                    )
                other = {k: v for k, v in updates.items() if k in ("name", "is_active")}
                if other:
                    self.audit.log(
                        AuditLogAction.USER_UPDATED,
                        user_id=result.id,
                        details={**other, "changed_by": current_user_id},
                    )
            return result


    # Felhasználó törlése
    def delete(self, user_id: int, current_user_id: int) -> None:
        with self._transaction():
            if user_id == current_user_id:
                raise ValueError("Saját magad nem törölheted.")
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            if user.is_owner:
                raise ValueError("Az ownert nem lehet törölni.")
            if self.session_repository is not None:
                self.session_repository.invalidate_all_for_user(user_id, updated_by=current_user_id)
            if self.audit:
                self.audit.log(
                    AuditLogAction.USER_DELETED,
                    user_id=user_id,
                    details={"email": user.email},
                )
            self.user_repository.delete(user_id, updated_by=current_user_id)


    # Jelszó elfelejtése
    def forgot_password(self, email: str, request_base_url: str | None = None) -> None:
        with self._transaction():
            user = self.user_repository.get_by_email(email.strip())
            if not user or not self.invite_token_repo:
                return

            self.invite_token_repo.invalidate_all_for_user(user.id, updated_by=user.id)
            invite_payload = new_invite_token_payload()
            self.invite_token_repo.create(
                user.id,
                invite_payload.token_hash,
                invite_payload.expires_at,
                created_by=user.id,
                updated_by=user.id,
            )

            set_password_link = build_set_password_link(request_base_url, invite_payload.raw_token)
            if set_password_link and self.email_service:
                self.email_service.send_set_password_invite(user.email, set_password_link)

            if self.audit:
                self.audit.log(
                    AuditLogAction.FORGOT_PASSWORD_LINK_SENT,
                    user_id=user.id,
                    details={"email": user.email},
                )
