# backend/core/modules/users/service/profile_service.py
# Feladat: A felhasználói profil application service-e. Profile update, locale/theme beállítás, demo-mode mezők és cache invalidáció logikáját kezeli a UserRepository fölött. Users profile service réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.service.audit_service import AuditService
from core.modules.users.domain.dto import User
from core.modules.users.domain.policies.profile_policy import (
    build_profile_payload,
    build_profile_updates,
    default_owner_settings,
    tenant_demo_mode_enabled,
)
from core.modules.users.domain.ports import BillingTrainingStatusPort, SessionRepositoryPort, UserEmailPort, UserRepositoryPort
from core.modules.users.cache import invalidate_user_cache
from core.modules.users.service._user_service_helpers import build_confirm_email_link, new_invite_token_payload
from core.kernel.runtime.clock import utc_now


class UserProfileService:
    def __init__(
        self,
        user_repository: UserRepositoryPort,
        *,
        email_service: UserEmailPort | None = None,
        session_repository: SessionRepositoryPort | None = None,
        audit_service: AuditService | None = None,
    ):
        self._user_repository = user_repository
        self._email_service = email_service
        self._session_repository = session_repository
        self._audit = audit_service

    def get_me(
        self,
        *,
        user: User,
        tenant,
        training_status_reader: BillingTrainingStatusPort | None = None,
    ) -> dict[str, object]:
        tenant_demo_mode = tenant_demo_mode_enabled(tenant)
        tenant_kb_has_training = True
        if training_status_reader is not None:
            tenant_kb_has_training = bool(training_status_reader.tenant_has_training_material(tenant))
        owner = self._user_repository.get_owner()
        return build_profile_payload(
            user,
            owner=owner,
            tenant_demo_mode=tenant_demo_mode,
            tenant_kb_has_training=tenant_kb_has_training,
            include_auth_context=True,
        )

    def get_default_settings(self) -> dict[str, str]:
        try:
            owner = self._user_repository.get_owner()
        except Exception:
            owner = None
        return default_owner_settings(owner)

    def update_me(
        self,
        *,
        user: User,
        name: str | None,
        preferred_locale: str | None,
        preferred_theme: str | None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        updates = build_profile_updates(
            name=name,
            preferred_locale=preferred_locale,
            preferred_theme=preferred_theme,
        )
        if not updates:
            owner = self._user_repository.get_owner()
            return build_profile_payload(user, owner=owner, include_auth_context=False)

        updated = user.with_updates(**updates)
        if not getattr(updated, "email", None):
            current = self._user_repository.get_by_id(user.id)
            if current and getattr(current, "email", None):
                updated = updated.with_updates(email=current.email)

        result = self._user_repository.update(updated, updated_by=updated_by if updated_by is not None else user.id)
        owner = self._user_repository.get_owner()
        return build_profile_payload(result, owner=owner, include_auth_context=False)

    def request_email_change(
        self,
        *,
        user: User,
        new_email: str,
        request_base_url: str | None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        normalized_email = new_email.strip()
        if not normalized_email:
            raise ValueError("email_required")
        if normalized_email.lower() == (user.email or "").strip().lower():
            raise ValueError("same_email")
        existing = self._user_repository.get_by_email(normalized_email)
        if existing and existing.id != user.id:
            raise ValueError("email_already_exists")

        if not getattr(user, "is_owner", False):
            result = self._user_repository.update(
                user.with_updates(
                    email=normalized_email,
                    pending_email=None,
                    pending_email_token_hash=None,
                    pending_email_expires_at=None,
                ),
                updated_by=updated_by if updated_by is not None else user.id,
            )
            if self._session_repository is not None:
                self._session_repository.invalidate_all_for_user(result.id, updated_by=updated_by if updated_by is not None else user.id)
            self._user_repository.increment_security_version(result.id, updated_by=updated_by if updated_by is not None else user.id)
            owner = self._user_repository.get_owner()
            return build_profile_payload(result, owner=owner, include_auth_context=False)

        token_payload = new_invite_token_payload()
        updated = user.with_updates(
            pending_email=normalized_email,
            pending_email_token_hash=token_payload.token_hash,
            pending_email_expires_at=token_payload.expires_at,
        )
        result = self._user_repository.update(updated, updated_by=updated_by if updated_by is not None else user.id)
        confirm_link = build_confirm_email_link(request_base_url, token_payload.raw_token)
        if confirm_link and self._email_service:
            owner = self._user_repository.get_owner()
            lang = getattr(result, "preferred_locale", None) or getattr(owner, "preferred_locale", None)
            self._email_service.send_email_change_confirmation(
                normalized_email,
                confirm_link,
                current_email=user.email,
                new_email=normalized_email,
                lang=lang,
            )
        owner = self._user_repository.get_owner()
        return build_profile_payload(result, owner=owner, include_auth_context=False)

    def confirm_email_change(self, *, token: str) -> User:
        token_hash = hashlib.sha256((token or "").encode()).hexdigest()
        user = self._user_repository.get_by_pending_email_token_hash(token_hash)
        if not user or not getattr(user, "pending_email", None):
            raise ValueError("invalid_email_change_token")
        expires_at = getattr(user, "pending_email_expires_at", None)
        if expires_at is None or expires_at < utc_now():
            raise ValueError("expired_email_change_token")

        new_email = str(user.pending_email).strip()
        existing = self._user_repository.get_by_email(new_email)
        if existing and existing.id != user.id:
            raise ValueError("email_already_exists")

        result = self._user_repository.update(
            user.with_updates(
                email=new_email,
                pending_email=None,
                pending_email_token_hash=None,
                pending_email_expires_at=None,
            ),
            updated_by=user.id,
        )
        if self._session_repository is not None:
            self._session_repository.invalidate_all_for_user(result.id, updated_by=result.id)
        self._user_repository.increment_security_version(result.id, updated_by=result.id)
        if self._audit is not None:
            self._audit.log(
                AuditLogAction.EMAIL_CONFIRMED,
                user_id=result.id,
                details={"old_value": user.email, "new_value": new_email, "email": new_email},
            )
        return result

    def invalidate_cache(self, tenant_slug: str | None, user_id: int) -> None:
        invalidate_user_cache(tenant_slug, user_id)
