from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.kernel.logging.observability import bind_observability_context, reset_observability_context
from core.kernel.events.dispatcher import EventDispatcher
from core.kernel.events.event_channel import SecurityAuditEventChannel
from core.kernel.events.handlers import register_security_audit_handlers
from core.kernel.events.outbox import OutboxWorkItem
from core.kernel.events.worker import OutboxWorker

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _OutboxStub:
    def __init__(self):
        self.appended = []
        self.due_events = []
        self.processed = []
        self.failed = []
        self.claimed_batches = []

    def append(self, *, event_type: str, payload: dict, idempotency_key: str | None = None):
        self.appended.append((event_type, payload, idempotency_key))
        return SimpleNamespace(id=len(self.appended))

    def claim_next_batch(self, *, limit: int = 100, stale_lock_after_sec: int = 300, lease_seconds: int = 300, lock_owner: str | None = None):
        self.claimed_batches.append((limit, stale_lock_after_sec, lease_seconds, lock_owner))
        batch = self.due_events[:limit]
        self.due_events = self.due_events[limit:]
        return [
            OutboxWorkItem(id=e.id, event_type=e.event_type, payload=dict(e.payload or {}))
            for e in batch
        ]

    def mark_processed(self, event_id: int):
        self.processed.append(event_id)

    def mark_failed(self, event_id: int, *, error: str, max_attempts: int, retry_delay_seconds: int):
        self.failed.append((event_id, error, max_attempts, retry_delay_seconds))


class _SecurityLoggerStub:
    def __init__(self):
        self.calls = []

    def login_successful_login(self, *args, **kwargs):
        self.calls.append(("login_successful_login", args, kwargs))


class _AuditServiceStub:
    def __init__(self):
        self.calls = []

    def log(self, action, **kwargs):
        self.calls.append((action, kwargs))


class _EmailServiceStub:
    def __init__(self, *, ok=True):
        self.ok = ok
        self.calls = []

    def send_2fa_code(self, *args, **kwargs):
        self.calls.append(("2fa", args, kwargs))
        return self.ok

    def send_set_password_invite(self, *args, **kwargs):
        self.calls.append(("invite", args, kwargs))
        return self.ok


def test_event_channel_persists_security_audit_and_email_events():
    outbox = _OutboxStub()
    channel = SecurityAuditEventChannel(
        _SecurityLoggerStub(),
        _AuditServiceStub(),
        _EmailServiceStub(),
        outbox_repository=outbox,
    )

    token = bind_observability_context(correlation_id="corr-1", request_id="req-1", tenant_id=7, user_id=1)
    try:
        channel.security_logger.login_successful_login(1, "127.0.0.1", "pytest", tenant_slug="demo")
        channel.audit_service.log(AuditLogAction.LOGIN_SUCCESS, user_id=1, tenant_slug="demo")
        channel.email_service.send_set_password_invite("user@example.com", "https://app.test/set-password?token=abc")
    finally:
        reset_observability_context(token)

    assert [item[0] for item in outbox.appended] == ["security", "audit", "email_invite"]
    assert outbox.appended[0][1]["_meta"]["correlation_id"] == "corr-1"
    assert outbox.appended[0][1]["_meta"]["request_id"] == "req-1"
    assert outbox.appended[0][1]["_meta"]["tenant_id"] == 7
    assert outbox.appended[1][1]["_meta"]["event_name"] == "audit"


def test_outbox_worker_marks_processed_on_success():
    outbox = _OutboxStub()
    security_logger = _SecurityLoggerStub()
    audit_service = _AuditServiceStub()
    email_service = _EmailServiceStub()
    outbox.due_events = [
        SimpleNamespace(
            id=1,
            event_type="audit",
            payload={
                "action": str(AuditLogAction.LOGIN_SUCCESS),
                "user_id": 1,
                "details": {"reason": "ok"},
                "ip": "127.0.0.1",
                "user_agent": "pytest",
                "tenant_slug": "demo",
                "_meta": {"correlation_id": "corr-2", "tenant_slug": "demo"},
            },
        ),
        SimpleNamespace(
            id=2,
            event_type="email_invite",
            payload={
                "to_email": "user@example.com",
                "set_password_link": "https://app.test/set-password?token=abc",
                "lang": None,
            },
        ),
        SimpleNamespace(
            id=3,
            event_type="security",
            payload={
                "method": "login_successful_login",
                "args": [1, "127.0.0.1", "pytest"],
                "kwargs": {"tenant_slug": "demo"},
            },
        ),
    ]
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=security_logger,
        audit_service=audit_service,
        email_service=email_service,
    )
    worker = OutboxWorker(outbox, dispatcher, lock_owner="test-worker")
    worker._process_batch()

    assert outbox.processed == [1, 2, 3]
    assert len(audit_service.calls) == 1
    assert len(email_service.calls) == 1
    assert len(security_logger.calls) == 1
    assert audit_service.calls[0][1]["correlation_id"] == "corr-2"


def test_outbox_worker_marks_failed_on_delivery_error():
    outbox = _OutboxStub()
    outbox.due_events = [
        SimpleNamespace(
            id=7,
            event_type="email_2fa",
            payload={
                "to_email": "user@example.com",
                "code": "123456",
                "pending_token": None,
                "lang": None,
                "expiry_minutes": 10,
            },
        )
    ]
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=_SecurityLoggerStub(),
        audit_service=_AuditServiceStub(),
        email_service=_EmailServiceStub(ok=False),
    )
    worker = OutboxWorker(
        outbox,
        dispatcher,
        max_retries=3,
        retry_delay_seconds=9,
        lock_owner="test-worker",
    )
    worker._process_batch()

    err = outbox.failed[0][1]
    assert "2FA" in err and "sikertelen" in err
    assert outbox.failed[0][0] == 7
    assert outbox.failed[0][2:] == (3, 9)
