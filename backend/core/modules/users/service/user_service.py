# backend/core/modules/users/service/user_service.py
# Feladat: A központi user application service. Admin user CRUD, jelszócsere, forgot password, audit log, permission/session invalidáció és cache törlés műveleteket fog össze. Nagy blast radiusú users service réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.modules.auth.repository.persistence.session_repository import SessionRepository
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.service.audit_service import AuditService
from core.infrastructure.email.email_service import EmailService
from core.modules.users.domain.dto.user import User
from core.modules.users.domain.ports import (
    InviteTokenRepositoryPort,
    SessionRepositoryPort,
    UserEmailPort,
    UserRepositoryPort,
)
from core.kernel.db.transactional_service import TransactionalService
from shared.validation.password import validate_password_policy
from core.modules.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload


def _normalize_invite_lang(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()[:2]
    return normalized if normalized in {"hu", "en", "es"} else None


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
    def change_password(
        self,
        *,
        user_id: int,
        current_password: str,
        new_password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
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
            if self.audit:
                self.audit.log(
                    AuditLogAction.PASSWORD_CHANGED,
                    user_id=user_id,
                    target_type="user",
                    target_id=str(user_id),
                    details={"email": getattr(user, "email", None), "changed_by": user_id},
                    ip=ip,
                    user_agent=user_agent,
                )

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
        invite_lang: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
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
            from core.kernel.runtime.clock import utc_now

            registration_completed_at = utc_now() if activate_immediately else None
            user = User.new(
                email=email,
                password_hash=password_hash,
                role=role,
                is_active=True,
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
                    owner = self.user_repository.get_owner()
                    lang = _normalize_invite_lang(invite_lang or getattr(owner, "preferred_locale", None))
                    self.email_service.send_set_password_invite(email, set_password_link, lang=lang)

            if self.audit:
                self.audit.log(
                    AuditLogAction.USER_CREATED,
                    user_id=created_by,
                    target_type="user",
                    target_id=str(created.id),
                    details={"email": email, "role": role, "created_by": created_by},
                    ip=ip,
                    user_agent=user_agent,
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
        request_base_url: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
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
                updates = {}
                if name is not None:
                    normalized_name = str(name).strip()
                    if normalized_name != str(user.name or "").strip():
                        updates["name"] = normalized_name
            else:
                updates = {}
                if name is not None:
                    normalized_name = str(name).strip()
                    if normalized_name != str(user.name or "").strip():
                        updates["name"] = normalized_name
                if is_active is not None:
                    if user_id == current_user_id:
                        raise ValueError("A saját fiók aktiválási állapotát nem módosíthatod.")
                    updates["is_active"] = is_active
                if email is not None:
                    existing = self.user_repository.get_by_email(email)
                    if existing and existing.id != user_id:
                        raise ValueError("Ez az email már használatban van.")
                    if email != user.email:
                        updates["email"] = email
                if role is not None:
                    if user_id == current_user_id and user.role == "admin" and role != "admin":
                        raise ValueError("A saját adminisztrátor szerepköröd nem módosítható.")
                    updates["role"] = role

            if not updates:
                return user

            result = self.user_repository.update(user.with_updates(**updates), updated_by=current_user_id)
            email_changed = email is not None and user.email != email
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
                        user_id=current_user_id,
                        target_type="user",
                        target_id=str(result.id),
                        details={
                            "old_value": user.email,
                            "new_value": email,
                            "changed_by": current_user_id,
                        },
                        ip=ip,
                        user_agent=user_agent,
                    )
                if role is not None and user.role != role:
                    self.audit.log(
                        AuditLogAction.USER_ROLE_CHANGED,
                        user_id=current_user_id,
                        target_type="user",
                        target_id=str(result.id),
                        details={
                            "old_value": user.role,
                            "new_value": role,
                            "changed_by": current_user_id,
                        },
                        ip=ip,
                        user_agent=user_agent,
                    )
                other = {k: v for k, v in updates.items() if k in ("name", "is_active")}
                if other:
                    previous = {key: getattr(user, key) for key in other}
                    self.audit.log(
                        AuditLogAction.USER_UPDATED,
                        user_id=current_user_id,
                        target_type="user",
                        target_id=str(result.id),
                        details={
                            **other,
                            "old_values": previous,
                            "new_values": other,
                            "changed_by": current_user_id,
                        },
                        ip=ip,
                        user_agent=user_agent,
                    )
            return result


    # Felhasználó törlése
    def delete(self, user_id: int, current_user_id: int, ip: str | None = None, user_agent: str | None = None) -> None:
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
                    user_id=current_user_id,
                    target_type="user",
                    target_id=str(user_id),
                    details={"email": user.email, "changed_by": current_user_id},
                    ip=ip,
                    user_agent=user_agent,
                )
            self.user_repository.delete(user_id, updated_by=current_user_id)


    # Jelszó elfelejtése
    def forgot_password(self, email: str, request_base_url: str | None = None, *, invite_lang: str | None = None) -> None:
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
                owner = self.user_repository.get_owner()
                lang = _normalize_invite_lang(
                    invite_lang or getattr(user, "preferred_locale", None) or getattr(owner, "preferred_locale", None)
                )
                self.email_service.send_set_password_invite(user.email, set_password_link, lang=lang)

            if self.audit:
                self.audit.log(
                    AuditLogAction.FORGOT_PASSWORD_LINK_SENT,
                    user_id=user.id,
                    details={"email": user.email},
                )
