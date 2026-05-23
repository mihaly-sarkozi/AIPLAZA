from __future__ import annotations

from datetime import UTC, datetime, timedelta
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


@pytest.mark.parametrize(
    ("method_name", "args", "allowed", "denied"),
    [
        (
            "can_use_channel_credential",
            lambda c, u, t: (c, "widget"),
            SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget"),
            SimpleNamespace(tenant_id=101, revoked=False, channel_type="api"),
        ),
        (
            "can_access_channel_kb",
            lambda c, u, t: (c, "kb-1"),
            SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget", allowed_kb_uuids=["kb-1"]),
            SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget", allowed_kb_uuids=["kb-2"]),
        ),
        (
            "can_send_channel_message",
            lambda c, u, t: (c, "widget", t),
            SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget"),
            SimpleNamespace(tenant_id=101, revoked=True, channel_type="widget"),
        ),
    ],
)
def test_chat_credential_permission_methods_have_allowed_and_denied_cases(method_name, args, allowed, denied) -> None:
    service = ChatPermissionService()
    tenant = SimpleNamespace(id=101)

    assert getattr(service, method_name)(*args(allowed, None, tenant)) is True
    assert getattr(service, method_name)(*args(denied, None, tenant)) is False


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("can_use_channel_credential", lambda credential, tenant: (credential, "widget", tenant.id)),
        ("can_send_channel_message", lambda credential, tenant: (credential, "widget", tenant)),
    ],
)
def test_chat_credential_permission_methods_deny_cross_tenant(method_name, args) -> None:
    service = ChatPermissionService()
    credential = SimpleNamespace(tenant_id=101, revoked=False, channel_type="widget")
    tenant = SimpleNamespace(id=202)

    assert getattr(service, method_name)(*args(credential, tenant)) is False


@pytest.mark.parametrize(
    ("method_name", "resource_factory"),
    [
        ("can_view_channel_admin", lambda tenant, credential: tenant),
        ("can_create_channel_credential", lambda tenant, credential: tenant),
        ("can_rotate_channel_credential", lambda tenant, credential: credential),
        ("can_revoke_channel_credential", lambda tenant, credential: credential),
    ],
)
def test_chat_admin_permission_methods_have_allowed_denied_cross_tenant_and_admin_scope(
    monkeypatch: pytest.MonkeyPatch,
    method_name,
    resource_factory,
) -> None:
    service = ChatPermissionService()
    admin_user = SimpleNamespace(id=1, tenant_id=101, role="admin")
    scoped_user = SimpleNamespace(id=2, tenant_id=101, role="user")
    denied_user = SimpleNamespace(id=3, tenant_id=101, role="user")
    cross_tenant_user = SimpleNamespace(id=4, tenant_id=202, role="admin")
    tenant = SimpleNamespace(id=101)
    credential = SimpleNamespace(tenant_id=101, revoked=False)
    resource = resource_factory(tenant, credential)
    monkeypatch.setattr(
        "apps.chat.service.chat_permission_service.has_permission",
        lambda user, permission: bool(user is scoped_user and permission == "chat.channel.manage"),
    )

    assert getattr(service, method_name)(admin_user, resource) is True
    assert getattr(service, method_name)(scoped_user, resource) is True
    assert getattr(service, method_name)(denied_user, resource) is False
    assert getattr(service, method_name)(cross_tenant_user, resource) is False


def test_chat_permission_service_denies_expired_credentials() -> None:
    service = ChatPermissionService()
    expired = SimpleNamespace(
        tenant_id=101,
        revoked=False,
        channel_type="widget",
        allowed_kb_uuids=["kb-1"],
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert service.can_use_channel_credential(expired, "widget", tenant_id=101) is False
    assert service.can_access_channel_kb(expired, "kb-1") is False
    assert service.can_send_channel_message(expired, "widget", SimpleNamespace(id=101)) is False


def test_chat_permission_service_denies_revoked_admin_credential_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    service = ChatPermissionService()
    admin_user = SimpleNamespace(id=1, tenant_id=101, role="admin")
    revoked = SimpleNamespace(tenant_id=101, revoked=True)
    monkeypatch.setattr(
        "apps.chat.service.chat_permission_service.has_permission",
        lambda _user, _permission: False,
    )

    assert service.can_rotate_channel_credential(admin_user, revoked) is False
    assert service.can_revoke_channel_credential(admin_user, revoked) is False
