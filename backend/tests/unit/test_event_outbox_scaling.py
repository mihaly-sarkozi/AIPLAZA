from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from core.platform.events.dispatcher import EventDispatcher
from core.platform.events.event_channel import SecurityAuditEventChannel
from core.platform.events.handlers import register_security_audit_handlers
from core.platform.events.worker import OutboxWorker

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

    def claim_next_batch(self, *, limit: int = 100, stale_lock_after_sec: int = 300, lock_owner: str | None = None):
        self.claimed_batches.append((limit, stale_lock_after_sec, lock_owner))
        batch = self.due_events[:limit]
        self.due_events = self.due_events[limit:]
        return [
            SimpleNamespace(
                id=e.id,
                event_type=e.event_type,
                payload=dict(e.payload or {}),
                attempts=getattr(e, "attempts", 0),
            )
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


def test_outbox_worker_uses_stale_lock_and_lock_owner():
    outbox = _OutboxStub()
    outbox.due_events = [SimpleNamespace(id=1, event_type="audit", payload={"action": "x"})]
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=_SecurityLoggerStub(),
        audit_service=_AuditServiceStub(),
        email_service=_EmailServiceStub(),
    )
    worker = OutboxWorker(outbox, dispatcher, batch_size=7, stale_lock_after_sec=123, lock_owner="worker-a")

    worker._process_batch()

    assert outbox.claimed_batches == [(7, 123, "worker-a")]


def test_outbox_worker_retry_and_idempotent_publisher_flow():
    outbox = _OutboxStub()
    outbox.due_events = [SimpleNamespace(id=2, event_type="email_2fa", payload={"to_email": "u@example.com", "code": "123456", "pending_token": None, "lang": None, "expiry_minutes": 10})]
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=_SecurityLoggerStub(),
        audit_service=_AuditServiceStub(),
        email_service=_EmailServiceStub(ok=False),
    )
    worker = OutboxWorker(outbox, dispatcher, max_retries=3, retry_delay_seconds=9, lock_owner="worker-a")

    worker._process_batch()

    assert outbox.failed[0][0] == 2
    assert outbox.failed[0][2:] == (3, 9)


def test_event_channel_append_reuses_idempotency_key():
    outbox = _OutboxStub()
    channel = SecurityAuditEventChannel(
        _SecurityLoggerStub(),
        _AuditServiceStub(),
        _EmailServiceStub(),
        outbox_repository=outbox,
    )

    channel.publish("audit", {"x": 1}, idempotency_key="dup")
    channel.publish("audit", {"x": 2}, idempotency_key="dup")

    assert [item[2] for item in outbox.appended] == ["dup", "dup"]


def test_outbox_worker_logs_correlation_metadata(caplog):
    outbox = _OutboxStub()
    outbox.due_events = [
        SimpleNamespace(
            id=5,
            event_type="audit",
            payload={
                "action": "login_success",
                "_meta": {
                    "correlation_id": "corr-5",
                    "request_id": "req-5",
                    "tenant_slug": "demo",
                    "tenant_id": 7,
                    "user_id": 11,
                },
            },
        )
    ]
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=_SecurityLoggerStub(),
        audit_service=_AuditServiceStub(),
        email_service=_EmailServiceStub(),
    )
    worker = OutboxWorker(outbox, dispatcher, lock_owner="worker-a")

    with caplog.at_level(logging.INFO, logger="core.outbox_worker"):
        worker._process_batch()

    # Egy esemény feldolgozása: batch_claimed → feldolgozás (audit) → outcome (success)
    started = [
        json.loads(record.message)
        for record in caplog.records
        if '"correlation_id": "corr-5"' in record.message
        and '"event_name": "audit"' in record.message
        and '"outcome"' not in record.message
    ][0]
    assert started["correlation_id"] == "corr-5"
    assert started["request_id"] == "req-5"
    assert started["tenant_id"] == 7
    assert started["user_id"] == 11
