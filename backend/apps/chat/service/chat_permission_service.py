# backend/apps/chat/service/chat_permission_service.py
# Feladat: Chat/channel permission boundary. Credential, tenant es channel
# scoped jogosultsagi dontesek kozponti helye.

from __future__ import annotations

from typing import Any


class ChatPermissionService:
    def can_use_channel_credential(
        self,
        credential: Any,
        channel: Any | None = None,
        *,
        tenant_id: int | None = None,
    ) -> bool:
        if credential is None:
            return False
        if tenant_id is not None and int(getattr(credential, "tenant_id", -1)) != int(tenant_id):
            return False
        if bool(getattr(credential, "revoked", False)):
            return False
        if channel is None:
            return True
        credential_channel = str(getattr(credential, "channel_type", "") or "").strip().lower()
        requested_channel = str(getattr(channel, "channel_type", channel) or "").strip().lower()
        return not requested_channel or credential_channel == requested_channel

    def can_access_channel_kb(self, credential: Any, kb_uuid: str | None) -> bool:
        requested_kb = str(kb_uuid or "").strip()
        allowed_kbs = [
            str(value).strip()
            for value in (getattr(credential, "allowed_kb_uuids", None) or [])
            if str(value or "").strip()
        ]
        if not allowed_kbs:
            return True
        return bool(requested_kb) and requested_kb in allowed_kbs

    def default_channel_kb(self, credential: Any) -> str | None:
        allowed_kbs = [
            str(value).strip()
            for value in (getattr(credential, "allowed_kb_uuids", None) or [])
            if str(value or "").strip()
        ]
        return allowed_kbs[0] if allowed_kbs else None


__all__ = ["ChatPermissionService"]
