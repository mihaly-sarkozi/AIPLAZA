from __future__ import annotations

from core.capabilities.users.dto import User
from core.capabilities.users.policies.profile_policy import (
    build_profile_payload,
    build_profile_updates,
    default_owner_settings,
    tenant_demo_mode_enabled,
)
from core.capabilities.users.ports import BillingTrainingStatusPort, UserRepositoryPort


class UserProfileService:
    def __init__(self, user_repository: UserRepositoryPort):
        self._user_repository = user_repository

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
        owner = self._user_repository.get_owner()
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
