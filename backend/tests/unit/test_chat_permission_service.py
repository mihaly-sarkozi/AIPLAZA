from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.chat.service.chat_permission_service import ChatPermissionService

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


def test_chat_permission_service_rejects_missing_or_revoked_credential() -> None:
    service = ChatPermissionService()

    assert service.can_use_channel_credential(None, "widget") is False
    assert service.can_use_channel_credential(SimpleNamespace(revoked=True, channel_type="widget"), "widget") is False


def test_chat_permission_service_checks_channel_scope() -> None:
    service = ChatPermissionService()

    assert service.can_use_channel_credential(SimpleNamespace(revoked=False, channel_type="widget"), "widget") is True
    assert service.can_use_channel_credential(SimpleNamespace(revoked=False, channel_type="api"), "widget") is False


def test_chat_permission_service_checks_tenant_scope() -> None:
    service = ChatPermissionService()
    credential = SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget")

    assert service.can_use_channel_credential(credential, "widget", tenant_id=101) is True
    assert service.can_use_channel_credential(credential, "widget", tenant_id=202) is False


def test_chat_permission_service_checks_kb_resource_scope() -> None:
    service = ChatPermissionService()
    credential = SimpleNamespace(tenant_id=101, allowed_kb_uuids=["kb-tenant-a"])

    assert service.can_access_channel_kb(credential, "kb-tenant-a") is True
    assert service.can_access_channel_kb(credential, "kb-tenant-b") is False
    assert service.default_channel_kb(credential) == "kb-tenant-a"


def test_chat_permission_service_allows_unscoped_credential_kb() -> None:
    service = ChatPermissionService()
    credential = SimpleNamespace(tenant_id=101, allowed_kb_uuids=[])

    assert service.can_access_channel_kb(credential, None) is True
    assert service.default_channel_kb(credential) is None


def test_chat_permission_service_names_channel_message_policy() -> None:
    service = ChatPermissionService()
    tenant = SimpleNamespace(id=101)
    credential = SimpleNamespace(tenant_id=101, revoked=False, channel_type="api")

    assert service.can_send_channel_message(credential, "api", tenant) is True
    assert service.can_send_channel_message(credential, "widget", tenant) is False
    assert service.can_send_channel_message(credential, "api", SimpleNamespace(id=202)) is False


def test_chat_permission_service_accepts_dict_credentials() -> None:
    service = ChatPermissionService()
    credential = {
        "tenant_id": 101,
        "revoked": False,
        "channel_type": "widget",
        "allowed_kb_uuids": ["kb-1"],
    }

    assert service.can_use_channel_credential(credential, "widget", tenant_id=101) is True
    assert service.can_access_channel_kb(credential, "kb-1") is True
    assert service.default_channel_kb(credential) == "kb-1"


def test_chat_permission_service_names_channel_admin_policies(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatPermissionService()
    user = SimpleNamespace(id=7, tenant_id=101)
    tenant = SimpleNamespace(id=101)
    credential = SimpleNamespace(tenant_id=101)

    monkeypatch.setattr(
        "apps.chat.service.chat_permission_service.has_permission",
        lambda current_user, permission: bool(current_user is user and permission == "chat.channel.manage"),
    )

    assert service.can_view_channel_admin(user, tenant) is True
    assert service.can_create_channel_credential(user, tenant) is True
    assert service.can_rotate_channel_credential(user, credential) is True
    assert service.can_revoke_channel_credential(user, credential) is True
    assert service.can_view_channel_admin(user, SimpleNamespace(id=202)) is False
