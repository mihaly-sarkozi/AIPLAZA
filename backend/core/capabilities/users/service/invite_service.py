# Meghívásos regisztrációs flow (token validálás, set-password, meghívó újraküldés).
# 2026.04.03 - Sárközi Mihály

from __future__ import annotations

import hashlib
from datetime import datetime

from passlib.hash import bcrypt_sha256 as pwd_hasher

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.capabilities.audit.service.audit_service import AuditService
from core.capabilities.email.email_service import EmailService
from core.capabilities.users.repositories.invite_token_repository import InviteTokenRepository
from core.capabilities.users.repositories.user_repository import UserRepository
from core.kernel.db.transactional_service import TransactionalService
from core.capabilities.users.service._user_service_helpers import build_set_password_link, new_invite_token_payload
from core.capabilities.users.service.invite_errors import InviteTokenExpiredError, InviteTokenInvalidError
from core.kernel.clock import utc_now


class InviteService(TransactionalService):
    
    # Meghívásos regisztrációs flow (token validálás, set-password, meghívó újraküldés).    
    def __init__(
        self,
        *,
        user_repository: UserRepository,
        invite_token_repository: InviteTokenRepository,
        audit_service: AuditService | None = None,
        email_service: EmailService | None = None,
        transaction_manager=None,
    ) -> None:
        super().__init__(transaction_manager=transaction_manager)
        self.user_repository = user_repository
        self.invite_token_repo = invite_token_repository
        self.audit = audit_service
        self.email_service = email_service

    # Meghívó token érvényességének ellenőrzése 
    def validate_invite_token(self, token: str) -> str:
        if not token:
            return "invalid"
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        record = self.invite_token_repo.get_by_token_hash(token_hash)
        if not record or record.used_at:
            return "invalid"
        if record.expires_at < utc_now():
            return "expired"
        return "valid"

    # Jelszó beállítása meghívó token alapján
    def set_password(self, token: str, password: str) -> None:
        with self._transaction():
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            record = self.invite_token_repo.get_by_token_hash(token_hash)
            if not record or record.used_at:
                raise InviteTokenInvalidError()
            if record.expires_at < utc_now():
                raise InviteTokenExpiredError()

            self.user_repository.update_password(record.user_id, pwd_hasher.hash(password), updated_by=record.user_id)
            self.invite_token_repo.mark_used(record.id, updated_by=record.user_id)
            user = self.user_repository.get_by_id(record.user_id)
            if user:
                updates = {
                    "is_active": True,
                    "registration_completed_at": utc_now(),
                    "failed_login_attempts": 0,
                }
                if not self.user_repository.exists_owner():
                    updates["role"] = "owner"
                self.user_repository.update(user.with_updates(**updates), updated_by=record.user_id)

            if self.audit:
                self.audit.log(
                    AuditLogAction.PASSWORD_SET_BY_INVITE,
                    user_id=record.user_id,
                    details={},
                )
    # Meghívó újraküldése
    def resend_invite(
        self,
        user_id: int,
        *,
        request_base_url: str | None = None,
        updated_by: int | None = None,
    ) -> None:
        with self._transaction():
            user = self.user_repository.get_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            if user.is_active:
                raise ValueError("A felhasználó már aktív. Csak inaktív (zárolt vagy megerősítésre váró) usereknek küldhető link.")
            if user.is_owner:
                raise ValueError("Az owner már aktív.")

            self.invite_token_repo.invalidate_all_for_user(user_id, updated_by=updated_by)
            invite_payload = new_invite_token_payload()
            self.invite_token_repo.create(
                user_id,
                invite_payload.token_hash,
                invite_payload.expires_at,
                created_by=updated_by,
                updated_by=updated_by,
            )

            set_password_link = build_set_password_link(request_base_url, invite_payload.raw_token)
            if set_password_link and self.email_service:
                self.email_service.send_set_password_invite(user.email, set_password_link)

            if self.audit:
                self.audit.log(
                    AuditLogAction.INVITE_RESENT,
                    user_id=user_id,
                    details={"email": user.email},
                )
