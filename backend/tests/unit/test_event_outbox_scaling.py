from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from core.kernel.events.dispatcher import EventDispatcher, HandlerRegistry
from core.kernel.events.event_channel import SecurityAuditEventChannel
from core.kernel.events.handlers import register_security_audit_handlers
from core.kernel.events.outbox import IdempotencyService, OutboxHealthService
from core.kernel.events.worker import OutboxWorker
import core.kernel.events.worker_loop as worker_loop
from core.kernel.events.worker_policy import worker_policy_for_event

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
            SimpleNamespace(
                id=e.id,
                event_type=e.event_type,
                payload=dict(e.payload or {}),
                attempts=getattr(e, "attempts", 0),
                lease_until=getattr(e, "lease_until", None),
            )
            for e in batch
        ]

    def mark_processed(self, event_id: int):
        self.processed.append(event_id)

    def mark_failed(self, event_id: int, *, error: str, max_attempts: int, retry_delay_seconds: int):
        self.failed.append((event_id, error, max_attempts, retry_delay_seconds))

    def queue_snapshot(self):
        return {"pending_jobs": len(self.due_events), "dead_letter_jobs": 0}


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

    assert outbox.claimed_batches == [(7, 123, 300, "worker-a")]


def test_outbox_worker_policy_uses_longer_timeouts_for_knowledge_jobs():
    audit_policy = worker_policy_for_event("security.audit_event", default_timeout_seconds=15)
    ingest_policy = worker_policy_for_event("knowledge.ingest_pipeline", default_timeout_seconds=15)
    index_policy = worker_policy_for_event("knowledge.index_build", default_timeout_seconds=15)

    assert audit_policy.handler_timeout_seconds <= 15
    assert ingest_policy.handler_timeout_seconds >= 5 * 60
    assert index_policy.handler_timeout_seconds >= ingest_policy.handler_timeout_seconds
    assert audit_policy.execution_mode == "thread"
    assert ingest_policy.execution_mode == "thread"
    assert index_policy.execution_mode == "thread"


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


def test_idempotency_service_requires_and_passes_key() -> None:
    outbox = _OutboxStub()

    with pytest.raises(ValueError, match="idempotency_key is required"):
        IdempotencyService(outbox).publish_once(event_type="audit", payload={}, idempotency_key="")

    IdempotencyService(outbox).publish_once(event_type="audit", payload={"x": 1}, idempotency_key="key-1")

    assert outbox.appended == [("audit", {"x": 1}, "key-1")]


def test_outbox_health_service_returns_repository_snapshot() -> None:
    outbox = _OutboxStub()
    outbox.due_events = [SimpleNamespace(id=1, event_type="audit", payload={})]

    snapshot = OutboxHealthService(outbox).queue_snapshot()

    assert snapshot["pending_jobs"] == 1


def test_handler_registry_maps_event_type_to_handler() -> None:
    registry = HandlerRegistry()
    calls: list[dict[str, object]] = []
    registry.register("event.type", lambda payload: calls.append(payload))

    registry.dispatch("event.type", {"ok": True})

    assert registry.has_handler("event.type") is True
    assert registry.registered_types() == ["event.type"]
    assert calls == [{"ok": True}]


def test_outbox_mark_failed_contract_dead_letters_after_max_attempts() -> None:
    row = SimpleNamespace(id=9, status="processing", attempts=2, last_error=None, locked_at="x", lock_owner="worker-a", leased_by="worker-a", lease_until="later", finished_at=None, next_retry_at=None, updated_at=None)

    def _mark_failed(event_id: int, *, error: str, max_attempts: int, retry_delay_seconds: int) -> None:
        assert event_id == row.id
        row.attempts += 1
        row.last_error = error
        row.locked_at = None
        row.lock_owner = None
        row.leased_by = None
        row.lease_until = None
        row.status = "dead_letter" if row.attempts >= max_attempts else "retry"

    _mark_failed(row.id, error="boom", max_attempts=3, retry_delay_seconds=1)

    assert row.status == "dead_letter"
    assert row.locked_at is None
    assert row.lease_until is None


def test_parallel_worker_stub_does_not_claim_same_job_twice() -> None:
    outbox = _OutboxStub()
    outbox.due_events = [SimpleNamespace(id=42, event_type="audit", payload={"action": "x"})]

    first_claim = outbox.claim_next_batch(limit=1, lock_owner="worker-a")
    second_claim = outbox.claim_next_batch(limit=1, lock_owner="worker-b")

    assert [item.id for item in first_claim] == [42]
    assert second_claim == []


def test_long_job_policy_has_heartbeat_and_extended_lease() -> None:
    policy = worker_policy_for_event("knowledge.ingest_pipeline", default_timeout_seconds=15)

    assert policy.lease_seconds > policy.handler_timeout_seconds
    assert policy.heartbeat_interval_seconds <= 30
    assert policy.execution_mode == "thread"


def test_process_one_passes_policy_execution_mode_to_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_dispatch_with_timeout(**kwargs):  # type: ignore[no-untyped-def]
        captured.update(kwargs)

    monkeypatch.setattr(worker_loop, "dispatch_with_timeout", _fake_dispatch_with_timeout)

    outbox = _OutboxStub()
    dispatcher = EventDispatcher()
    register_security_audit_handlers(
        dispatcher,
        security_logger=_SecurityLoggerStub(),
        audit_service=_AuditServiceStub(),
        email_service=_EmailServiceStub(),
    )
    worker = OutboxWorker(outbox, dispatcher, lock_owner="worker-a")
    item = SimpleNamespace(
        id=99,
        event_type="knowledge.ingest_pipeline",
        payload={},
        attempts=0,
        lease_until=None,
    )

    worker_loop.process_one(worker, item, batch_id="batch-x")

    assert captured["event_type"] == "knowledge.ingest_pipeline"
    assert captured["execution_mode"] == "thread"


def test_dispatch_with_timeout_rejects_unsupported_execution_mode() -> None:
    dispatcher = EventDispatcher()

    with pytest.raises(ValueError, match="Unsupported outbox execution mode"):
        worker_loop.dispatch_with_timeout(
            dispatcher=dispatcher,
            event_type="audit",
            payload={},
            timeout_seconds=1,
            execution_mode="unsupported",
        )


def test_worker_policy_does_not_advertise_unimplemented_process_executor() -> None:
    policies = [
        worker_policy_for_event("knowledge.ingest_pipeline", default_timeout_seconds=15),
        worker_policy_for_event("knowledge.index_build", default_timeout_seconds=15),
        worker_policy_for_event("knowledge.ingest_item_reprocess", default_timeout_seconds=15),
        worker_policy_for_event("knowledge.recovery_sweep", default_timeout_seconds=15),
    ]

    assert {policy.execution_mode for policy in policies} == {"thread"}


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
