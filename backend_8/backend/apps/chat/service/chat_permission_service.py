# backend/apps/chat/service/chat_permission_service.py
# Feladat: Chat/channel permission boundary. Credential, tenant es channel
# scoped jogosultsagi dontesek kozponti helye.

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.modules.auth.web.dependencies.auth_dependencies import has_permission


def _safe_has_permission(user: Any | None, permission: str) -> bool:
    try:
        return has_permission(user, permission)
    except RuntimeError:
        return False


class ChatPermissionService:
    def can_use_channel_credential(
        self,
        credential: Any,
        channel: Any | None = None,
        tenant_id: int | None = None,
    ) -> bool:
        if credential is None:
            return False
        credential_tenant_id = self._value(credential, "tenant_id")
        if tenant_id is not None and int(credential_tenant_id or -1) != int(tenant_id):
            return False
        if self._credential_is_revoked(credential) or self._credential_is_expired(credential):
            return False
        if channel is None:
            return True
        credential_channel = str(self._value(credential, "channel_type", "") or "").strip().lower()
        requested_channel = str(self._value(channel, "channel_type", channel) or "").strip().lower()
        return not requested_channel or credential_channel == requested_channel

    def can_access_channel_kb(self, credential: Any, kb_uuid: str | None) -> bool:
        if credential is None or self._credential_is_revoked(credential) or self._credential_is_expired(credential):
            return False
        requested_kb = str(kb_uuid or "").strip()
        allowed_kbs = [
            str(value).strip()
            for value in (self._value(credential, "allowed_kb_uuids") or [])
            if str(value or "").strip()
        ]
        if not allowed_kbs:
            return True
        return bool(requested_kb) and requested_kb in allowed_kbs

    def can_send_channel_message(self, credential: Any, channel: Any | None, tenant: Any | None) -> bool:
        tenant_id = self._tenant_id(tenant)
        return self.can_use_channel_credential(credential, channel, tenant_id=tenant_id)

    def can_view_channel_admin(self, user: Any | None, tenant: Any | None) -> bool:
        return self._has_channel_admin_permission(user, tenant)

    def can_create_channel_credential(self, user: Any | None, tenant: Any | None) -> bool:
        return self._has_channel_admin_permission(user, tenant)

    def can_rotate_channel_credential(self, user: Any | None, credential: Any | None) -> bool:
        if credential is None or self._credential_is_revoked(credential):
            return False
        return self._has_channel_admin_permission(user, credential)

    def can_revoke_channel_credential(self, user: Any | None, credential: Any | None) -> bool:
        if credential is None or self._credential_is_revoked(credential):
            return False
        return self._has_channel_admin_permission(user, credential)

    def default_channel_kb(self, credential: Any) -> str | None:
        allowed_kbs = [
            str(value).strip()
            for value in (self._value(credential, "allowed_kb_uuids") or [])
            if str(value or "").strip()
        ]
        return allowed_kbs[0] if allowed_kbs else None

    @staticmethod
    def _value(value: Any | None, key: str, default: Any = None) -> Any:
        if isinstance(value, dict):
            return value.get(key, default)
        return getattr(value, key, default)

    @classmethod
    def _tenant_id(cls, value: Any | None) -> int | None:
        if value is None:
            return None
        raw = cls._value(value, "tenant_id")
        if raw is None:
            raw = cls._value(value, "id")
        try:
            tenant_id = int(raw)
        except (TypeError, ValueError):
            return None
        return tenant_id if tenant_id > 0 else None

    @classmethod
    def _credential_is_revoked(cls, credential: Any | None) -> bool:
        return bool(cls._value(credential, "revoked", False) or cls._value(credential, "revoked_at", None))

    @classmethod
    def _credential_is_expired(cls, credential: Any | None) -> bool:
        expires_at = cls._value(credential, "expires_at", None)
        if expires_at is None:
            return False
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                return True
        if not isinstance(expires_at, datetime):
            return False
        now = datetime.now(UTC)
        if expires_at.tzinfo is None:
            now = now.replace(tzinfo=None)
        return expires_at <= now

    def _has_channel_admin_permission(self, user: Any | None, scoped_resource: Any | None) -> bool:
        if user is None:
            return False
        if not (self._role(user) in {"owner", "admin"} or _safe_has_permission(user, "chat.channel.manage")):
            return False
        user_tenant_id = self._value(user, "tenant_id")
        try:
            user_tenant_id = int(user_tenant_id) if user_tenant_id is not None else None
        except (TypeError, ValueError):
            user_tenant_id = None
        resource_tenant_id = self._tenant_id(scoped_resource)
        if user_tenant_id is None or resource_tenant_id is None:
            return True
        return user_tenant_id == resource_tenant_id

    @staticmethod
    def _role(user: Any | None) -> str:
        return str(getattr(user, "role", "") or "").strip().lower()


__all__ = ["ChatPermissionService"]
