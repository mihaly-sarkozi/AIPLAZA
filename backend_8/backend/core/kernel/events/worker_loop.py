# backend/core/kernel/events/worker_loop.py
# Feladat: Az outbox worker tényleges poll, batch és egyedi esemény feldolgozó algoritmusát tartalmazza. Claimeli a sorokat, observability contextet állít, timeouttal dispatchol, majd processed vagy failed állapotba teszi az eseményeket. Belső core futtatási logika, amelyet az OutboxWorker osztály vékony életciklus burka hív.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import threading
import uuid
from typing import TYPE_CHECKING

from core.kernel.runtime.instance_role import get_instance_role
from core.kernel.logging.observability import (
    increment_metric,
    log_exception_event,
    log_structured_event,
    observability_scope,
)
from core.kernel.events.worker_policy import worker_policy_for_event

if TYPE_CHECKING:
    from core.kernel.events.dispatcher import EventDispatcher
    from core.kernel.events.outbox import OutboxWorkItem, PlatformEventOutboxRepository


def run_poll_loop(worker: "OutboxWorkerProtocol") -> None:
    """Főciklus: eseményeket kérdez le és dispatchol, amíg le nem állítják."""
    while not worker.stop_event.is_set():
        try:
            processed = process_batch(worker)
            if processed == 0:
                worker.stop_event.wait(worker.poll_interval)
        except Exception as exc:
            log_exception_event(
                "core.outbox_worker",
                "outbox_worker.poll_loop_failed",
                exc,
                worker_run_id=worker.worker_run_id,
                worker_role="worker",
                lock_owner=worker.lock_owner,
            )
            worker.stop_event.wait(worker.poll_interval)


def process_batch(worker: "OutboxWorkerProtocol") -> int:
    batch_id = uuid.uuid4().hex
    items = worker.outbox.claim_next_batch(
        limit=worker.batch_size,
        stale_lock_after_sec=worker.stale_lock_after_sec,
        lease_seconds=worker.lease_seconds,
        lock_owner=worker.lock_owner,
    )
    if items:
        increment_metric("platform.outbox.batch.count", 1.0)
        increment_metric("platform.outbox.claimed.count", float(len(items)), tags={"lock_owner": worker.lock_owner})
        log_structured_event(
            "core.outbox_worker",
            "outbox_worker.batch_claimed",
            batch_id=batch_id,
            claimed_count=len(items),
            stale_lock_after_sec=worker.stale_lock_after_sec,
            worker_run_id=worker.worker_run_id,
            worker_role="worker",
            lock_owner=worker.lock_owner,
        )
    for item in items:
        process_one(worker, item, batch_id=batch_id)
    return len(items)


def process_one(worker: "OutboxWorkerProtocol", item: "OutboxWorkItem", *, batch_id: str) -> None:
    meta = dict((item.payload or {}).get("_meta") or {})
    with observability_scope(
        correlation_id=meta.get("correlation_id"),
        request_id=meta.get("request_id"),
        tenant_id=meta.get("tenant_id"),
        tenant_slug=meta.get("tenant_slug"),
        user_id=meta.get("user_id"),
        event_name=item.event_type,
        worker_run_id=worker.worker_run_id,
        worker_role="worker",
        batch_id=batch_id,
        instance_role=_instance_role_value(),
    ):
        log_structured_event(
            "core.outbox_worker",
            "outbox_worker.event_started",
            event_id=item.id,
            event_type=item.event_type,
            retry_count=item.attempts,
            lease_until=item.lease_until.isoformat() if item.lease_until else None,
            batch_id=batch_id,
            lock_owner=worker.lock_owner,
        )
        policy = worker_policy_for_event(
            item.event_type,
            default_timeout_seconds=worker.handler_timeout_seconds,
        )
        try:
            dispatch_with_timeout(
                outbox=worker.outbox,
                event_id=item.id,
                lock_owner=worker.lock_owner,
                dispatcher=worker.dispatcher,
                event_type=item.event_type,
                payload=item.payload or {},
                timeout_seconds=policy.handler_timeout_seconds,
                lease_seconds=policy.lease_seconds,
                heartbeat_interval_seconds=policy.heartbeat_interval_seconds,
                execution_mode=policy.execution_mode,
            )
            worker.outbox.mark_processed(item.id)
            increment_metric("platform.outbox.processed.count", 1.0, tags={"event_type": item.event_type})
            log_structured_event(
                "core.outbox_worker",
                "outbox_worker.event_processed",
                event_id=item.id,
                event_type=item.event_type,
                retry_count=item.attempts,
                timeout_sec=policy.handler_timeout_seconds,
                batch_id=batch_id,
                lock_owner=worker.lock_owner,
                outcome="success",
            )
        except Exception as exc:
            increment_metric("platform.outbox.failed.count", 1.0, tags={"event_type": item.event_type})
            increment_metric("platform.worker.retry.count", 1.0, tags={"event_type": item.event_type})
            log_exception_event(
                "core.outbox_worker",
                "outbox_worker.event_failed",
                exc,
                event_id=item.id,
                event_type=item.event_type,
                retry_count=item.attempts + 1,
                timeout_sec=policy.handler_timeout_seconds,
                batch_id=batch_id,
                lock_owner=worker.lock_owner,
                outcome="failure",
            )
            worker.outbox.mark_failed(
                item.id,
                error=str(exc),
                max_attempts=worker.max_retries,
                retry_delay_seconds=worker.retry_delay_seconds,
            )


def dispatch_with_timeout(
    *,
    outbox: object | None = None,
    event_id: int | None = None,
    lock_owner: str | None = None,
    dispatcher: object,
    event_type: str,
    payload: dict,
    timeout_seconds: int,
    lease_seconds: int | None = None,
    heartbeat_interval_seconds: int | None = None,
    execution_mode: str = "thread",
) -> None:
    if execution_mode != "thread":
        raise ValueError(f"Unsupported outbox execution mode: {execution_mode}")

    error_holder: list[Exception] = []
    done = threading.Event()

    def _target() -> None:
        try:
            dispatcher.dispatch(event_type, payload)
        except Exception as exc:  # pragma: no cover - propagated below
            error_holder.append(exc)
        finally:
            done.set()

    def _heartbeat_target() -> None:
        heartbeat = getattr(outbox, "heartbeat", None)
        if not callable(heartbeat) or event_id is None or lease_seconds is None:
            return
        interval = max(5, int(heartbeat_interval_seconds or 30))
        while not done.wait(interval):
            try:
                heartbeat(event_id, lock_owner=lock_owner, lease_seconds=max(1, int(lease_seconds)))
                increment_metric("platform.outbox.heartbeat.count", 1.0, tags={"event_type": event_type})
            except Exception as exc:
                log_exception_event(
                    "core.outbox_worker",
                    "outbox_worker.heartbeat_failed",
                    exc,
                    event_id=event_id,
                    event_type=event_type,
                    lock_owner=lock_owner,
                )

    thread = threading.Thread(target=_target, daemon=True, name=f"outbox-dispatch-{event_type}")
    heartbeat_thread = threading.Thread(
        target=_heartbeat_target,
        daemon=True,
        name=f"outbox-heartbeat-{event_type}",
    )
    thread.start()
    heartbeat_thread.start()
    thread.join(timeout=float(timeout_seconds))
    if thread.is_alive():
        done.set()
        increment_metric("outbox.handler_timeout_total", 1.0, tags={"event_type": event_type})
        raise TimeoutError(
            f"Outbox handler timeout ({timeout_seconds}s) event_type={event_type}"
        )
    if error_holder:
        raise error_holder[0]


def _instance_role_value() -> str | None:
    try:
        return get_instance_role().value
    except Exception:
        return None


class OutboxWorkerProtocol:
    outbox: "PlatformEventOutboxRepository"
    dispatcher: "EventDispatcher"
    poll_interval: float
    max_retries: int
    retry_delay_seconds: int
    batch_size: int
    stale_lock_after_sec: int
    handler_timeout_seconds: int
    lease_seconds: int
    lock_owner: str | None
    worker_run_id: str
    stop_event: threading.Event


__all__ = [
    "dispatch_with_timeout",
    "process_batch",
    "process_one",
    "run_poll_loop",
]
