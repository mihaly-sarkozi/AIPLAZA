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
