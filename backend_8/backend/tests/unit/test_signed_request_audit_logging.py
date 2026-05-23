from __future__ import annotations

import apps.chat.application.http_use_cases as chat_use_cases

import pytest

pytestmark = pytest.mark.unit


def test_canonical_signed_request_reason_mapping() -> None:
    assert chat_use_cases._canonical_signed_request_reason("missing_signature_headers: Missing headers") == "missing_signature"
    assert chat_use_cases._canonical_signed_request_reason("missing_ip_allowlist: denied") == "ip_not_allowed"
    assert chat_use_cases._canonical_signed_request_reason("credential_revoked: revoked") == "credential_revoked"
    assert chat_use_cases._canonical_signed_request_reason("credential_expired: expired") == "credential_expired"


def test_audit_channel_policy_rejection_masks_ip_and_logs_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    structured_calls: list[tuple[str, str, dict]] = []
    audit_calls: list[dict] = []

    def _structured_stub(domain: str, event: str, **kwargs) -> None:
        structured_calls.append((domain, event, kwargs))

    class _AuditStub:
        def log(self, *args, **kwargs) -> None:
            audit_calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(chat_use_cases, "log_structured_event", _structured_stub)

    chat_use_cases.audit_channel_policy_rejection(
        reason="invalid_signature: Invalid channel request signature.",
        tenant_id=7,
        channel_id=99,
        credential_id=99,
        remote_ip="198.51.100.12",
        path="/api/channel/chat",
        method="POST",
        request_id="req-test-1",
        timestamp="2026-05-22T12:00:00+00:00",
        audit=_AuditStub(),
    )

    assert structured_calls
    _, _, structured_kwargs = structured_calls[0]
    assert structured_kwargs["reason_code"] == "invalid_signature"
    assert structured_kwargs["tenant_id"] == 7
    assert structured_kwargs["channel_id"] == 99
    assert structured_kwargs["credential_id"] == 99
    assert structured_kwargs["request_id"] == "req-test-1"
    assert structured_kwargs["timestamp"] == "2026-05-22T12:00:00+00:00"
    assert structured_kwargs["client_ip_hash"]
    assert structured_kwargs["client_ip_hash"] != "198.51.100.12"

    assert audit_calls
    details = audit_calls[0]["kwargs"]["details"]
    assert details["tenant_id"] == 7
    assert details["channel_id"] == 99
    assert details["credential_id"] == 99
    assert details["reason"] == "invalid_signature"
    assert details["request_id"] == "req-test-1"
    assert details["timestamp"] == "2026-05-22T12:00:00+00:00"
    assert details["client_ip_hash"]
    assert details["client_ip_hash"] != "198.51.100.12"
