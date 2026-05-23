from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import time
from dataclasses import dataclass

import pytest

from apps.chat.channel_access import ChannelAccessRepository, ChannelPrincipal
from apps.chat.channel_policy import normalize_ip_ranges, remote_ip_allowed, verify_channel_signature

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass(slots=True)
class _TenantRef:
    tenant_id: int
    slug: str


@dataclass(slots=True)
class _KnowledgeBaseRef:
    uuid: str
    tenant: _TenantRef


def tenant_factory(*, tenant_id: int, slug: str) -> _TenantRef:
    return _TenantRef(tenant_id=tenant_id, slug=slug)


def knowledge_base_factory(*, tenant: _TenantRef, uuid: str) -> _KnowledgeBaseRef:
    return _KnowledgeBaseRef(uuid=uuid, tenant=tenant)


def test_widget_origin_normalization_defaults_to_https() -> None:
    normalized = ChannelAccessRepository._normalize_widget_origin("pelda.hu")
    assert normalized == "https://pelda.hu"


def test_widget_origin_wildcard_rejected() -> None:
    with pytest.raises(ValueError):
        ChannelAccessRepository._normalize_widget_origin("https://*.pelda.hu")


def test_origin_value_requires_scheme_and_host() -> None:
    assert ChannelAccessRepository._origin_value("https://www.pelda.hu/path?q=1") == "https://www.pelda.hu"
    assert ChannelAccessRepository._origin_value("not-a-url") == ""


def test_normalize_ip_ranges_accepts_cidr_and_single_ip() -> None:
    assert normalize_ip_ranges(["192.0.2.4", "10.0.0.0/24"]) == ["192.0.2.4", "10.0.0.0/24"]
    assert remote_ip_allowed("10.0.0.42", ["10.0.0.0/24"]) is True
    assert remote_ip_allowed("10.0.1.42", ["10.0.0.0/24"]) is False


def test_channel_signature_accepts_once_and_rejects_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("apps.chat.channel_policy.get_rate_limit_redis", lambda: None)
    secret = "ck_test.secret"
    body = b'{"question":"hello"}'
    timestamp = str(int(time.time()))
    nonce = "nonce-value-123"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(["POST", "/api/channel/chat", timestamp, nonce, body_hash]).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    assert verify_channel_signature(
        secret=secret,
        method="POST",
        path="/api/channel/chat",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        credential_id=123,
    )[0] is True

    replay_allowed, replay_reason = verify_channel_signature(
        secret=secret,
        method="POST",
        path="/api/channel/chat",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        credential_id=123,
    )
    assert replay_allowed is False
    assert replay_reason.startswith("reused_nonce:")


def test_channel_signature_fails_closed_without_redis_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr("apps.chat.channel_policy.get_rate_limit_redis", lambda: None)
    secret = "ck_test.secret"
    body = b'{"question":"hello"}'
    timestamp = str(int(time.time()))
    nonce = "nonce-value-456"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(["POST", "/api/channel/chat", timestamp, nonce, body_hash]).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    allowed, reason = verify_channel_signature(
        secret=secret,
        method="POST",
        path="/api/channel/chat",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        credential_id=456,
    )

    assert allowed is False
    assert reason.startswith("redis_unavailable:")


def test_channel_signature_rejects_invalid_body_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr("apps.chat.channel_policy.get_rate_limit_redis", lambda: None)
    secret = "ck_test.secret"
    body = b'{"question":"hello"}'
    timestamp = str(int(time.time()))
    nonce = "nonce-value-789"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join(["POST", "/api/channel/chat", timestamp, nonce, body_hash]).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()

    allowed, reason = verify_channel_signature(
        secret=secret,
        method="POST",
        path="/api/channel/chat",
        body=body,
        timestamp=timestamp,
        nonce=nonce,
        signature=signature,
        body_hash="0" * 64,
        credential_id=789,
    )

    assert allowed is False
    assert reason.startswith("invalid_body_hash:")


def test_channel_signature_rejects_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setattr("apps.chat.channel_policy.get_rate_limit_redis", lambda: None)

    allowed, reason = verify_channel_signature(
        secret="ck_test.secret",
        method="POST",
        path="/api/channel/chat",
        body=b"{}",
        timestamp=str(int(time.time())),
        nonce="nonce-value-bad-signature",
        signature="sha256=not-valid",
        credential_id=790,
    )

    assert allowed is False
    assert reason.startswith("invalid_signature:")


def test_api_authorization_rejects_ip_not_allowed() -> None:
    repo = ChannelAccessRepository(lambda: None)
    principal = ChannelPrincipal(
        tenant_id=1,
        credential_id=10,
        channel_type="api",
        allowed_kb_uuids=[],
        daily_limit=100,
        per_minute_limit=10,
        allowed_origins=[],
        allowed_ip_ranges=["10.0.0.0/24"],
        require_signed_requests=False,
        presented_secret="ck_test.secret",
    )

    allowed, reason = repo.authorize_api_request(
        principal,
        remote_ip="192.0.2.10",
        method="POST",
        path="/api/channel/chat",
        body=b"{}",
        timestamp=None,
        nonce=None,
        signature=None,
    )

    assert allowed is False
    assert reason.startswith("missing_ip_allowlist:")


def test_tenant_channel_credential_scope_is_bound_to_principal_tenant() -> None:
    principal = ChannelPrincipal(
        tenant_id=1,
        credential_id=10,
        channel_type="api",
        allowed_kb_uuids=["tenant-a-kb"],
        daily_limit=100,
        per_minute_limit=10,
        allowed_origins=[],
        allowed_ip_ranges=["192.0.2.10"],
        require_signed_requests=False,
        presented_secret="ck_test.secret",
    )

    assert principal.tenant_id == 1
    assert "tenant-b-kb" not in principal.allowed_kb_uuids


def test_tenant_a_credential_scope_rejects_tenant_b_channel_kb() -> None:
    tenant_a = tenant_factory(tenant_id=1, slug="tenant-a")
    tenant_b = tenant_factory(tenant_id=2, slug="tenant-b")
    kb_a = knowledge_base_factory(tenant=tenant_a, uuid="kb-tenant-a")
    kb_b = knowledge_base_factory(tenant=tenant_b, uuid="kb-tenant-b")
    principal = ChannelPrincipal(
        tenant_id=tenant_a.tenant_id,
        credential_id=99,
        channel_type="api",
        allowed_kb_uuids=[kb_a.uuid],
        daily_limit=100,
        per_minute_limit=10,
        allowed_origins=[],
        allowed_ip_ranges=["192.0.2.10"],
        require_signed_requests=False,
        presented_secret="ck_test.secret",
    )

    allowed_kbs = [value for value in principal.allowed_kb_uuids if value]
    requested_kb = kb_b.uuid

    assert requested_kb not in allowed_kbs


def test_quota_exceeded_rejects_after_daily_limit() -> None:
    repo = ChannelAccessRepository(lambda: None)

    first, _, _ = repo.reserve_usage_slot(tenant_id=1, credential_id=10, daily_limit=1, per_minute_limit=100)
    second, reason, _ = repo.reserve_usage_slot(tenant_id=1, credential_id=10, daily_limit=1, per_minute_limit=100)

    assert first is True
    assert second is False
    assert "napi" in reason.lower()


def test_expired_credential_time_boundary_model() -> None:
    principal = ChannelPrincipal(
        tenant_id=1,
        credential_id=10,
        channel_type="api",
        allowed_kb_uuids=[],
        daily_limit=100,
        per_minute_limit=10,
        allowed_origins=[],
        allowed_ip_ranges=["192.0.2.10"],
        require_signed_requests=False,
        presented_secret="ck_test.secret",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )

    assert principal.expires_at is not None
    assert principal.expires_at < datetime.now(UTC)


def test_rotation_window_accepts_old_and_new_secret_versions() -> None:
    repo = ChannelAccessRepository(lambda: None)
    now = datetime.now(UTC)
    old_secret = "ck_old.secret-old"
    new_secret = "ck_new.secret-new"

    active_version = repo._resolve_secret_version(
        prefix="ck_old",
        incoming_hash=repo._hash_secret(old_secret),
        active_prefix="ck_old",
        active_hash=repo._hash_secret(old_secret),
        next_prefix="ck_new",
        next_hash=repo._hash_secret(new_secret),
        rotating_until=now + timedelta(minutes=5),
        now=now,
    )
    next_version = repo._resolve_secret_version(
        prefix="ck_new",
        incoming_hash=repo._hash_secret(new_secret),
        active_prefix="ck_old",
        active_hash=repo._hash_secret(old_secret),
        next_prefix="ck_new",
        next_hash=repo._hash_secret(new_secret),
        rotating_until=now + timedelta(minutes=5),
        now=now,
    )

    assert active_version == "active"
    assert next_version == "next"


def test_rotation_promotion_rejects_old_secret_after_window() -> None:
    repo = ChannelAccessRepository(lambda: None)
    now = datetime.now(UTC)
    # Minimal mutable row stub az ORM mezőkkel.
    row = type(
        "RowStub",
        (),
        {
            "key_prefix": "ck_old",
            "active_secret_hash": repo._hash_secret("ck_old.secret-old"),
            "secret_hash": repo._hash_secret("ck_old.secret-old"),
            "next_key_prefix": "ck_new",
            "next_secret_hash": repo._hash_secret("ck_new.secret-new"),
            "rotating_until": now - timedelta(seconds=1),
            "secret_version": "rotating",
        },
    )()

    promoted = repo._promote_next_secret_if_due(row, now=now)
    assert promoted is True
    assert row.key_prefix == "ck_new"
    assert row.next_key_prefix is None
    assert row.next_secret_hash is None
    assert row.rotating_until is None
    assert row.secret_version == "active"

    old_version = repo._resolve_secret_version(
        prefix="ck_old",
        incoming_hash=repo._hash_secret("ck_old.secret-old"),
        active_prefix=row.key_prefix,
        active_hash=row.active_secret_hash,
        next_prefix=str(row.next_key_prefix or ""),
        next_hash=str(row.next_secret_hash or ""),
        rotating_until=row.rotating_until,
        now=now,
    )
    new_version = repo._resolve_secret_version(
        prefix="ck_new",
        incoming_hash=repo._hash_secret("ck_new.secret-new"),
        active_prefix=row.key_prefix,
        active_hash=row.active_secret_hash,
        next_prefix=str(row.next_key_prefix or ""),
        next_hash=str(row.next_secret_hash or ""),
        rotating_until=row.rotating_until,
        now=now,
    )
    assert old_version is None
    assert new_version == "active"


