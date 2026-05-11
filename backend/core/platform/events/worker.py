"""Outbox worker – önállóan futtatható esemény-feldolgozó.

Ez a modul biztosítja az OutboxWorker osztályt, amely kétféleképpen futtatható:

  1. Szálként (thread mód) – fejlesztői combined módban:
        worker.start_thread()   # háttérszálat indít
        worker.stop()           # jelzi a leállást, megvárja a szálat

  2. Blokkoló módban (standalone process) – skálázott deploymentben:
        worker.run_blocking()   # az aktuális szálban fut, SIGTERM/SIGINT-ra megáll

Skálázott deploymentben (INSTANCE_ROLE=worker):
    INSTANCE_ROLE=worker python -m core.platform.events

A worker feladata:
  - Atomikus ``claim_next_batch`` (SKIP LOCKED + lock) veszi át a sorokat
  - Minden eseményt az EventDispatcher-en keresztül routol a megfelelő handler-ekhez
  - Sikeres feldolgozás esetén mark_processed, hiba esetén mark_failed
  - Exponenciális visszatartással újrapróbál max_retries-szor

FONTOS: Web-processben (INSTANCE_ROLE=web) NE indítsunk OutboxWorker-t.
A web-process csak az outbox-ba ír (publish), a feldolgozás a worker-processben történik.
"""
from __future__ import annotations

import logging
import threading
import uuid
from typing import TYPE_CHECKING

from core.kernel.config.instance_role import get_instance_role
from core.kernel.logging.observability import (
    increment_metric,
    log_exception_event,
    log_structured_event,
    observability_scope,
)

if TYPE_CHECKING:
    from core.platform.events.dispatcher import EventDispatcher
    from core.platform.events.outbox import PlatformEventOutboxRepository, OutboxWorkItem

_log = logging.getLogger(__name__)

DEFAULT_STALE_LOCK_SEC = 300

DEFAULT_POLL_INTERVAL_SEC = 1.0
DEFAULT_MAX_RETRIES = 10
DEFAULT_RETRY_DELAY_SEC = 5
DEFAULT_BATCH_SIZE = 100


def default_outbox_lock_owner() -> str:
    """Egyedi példányazonosító lock_ownerhez (több worker / horizontális skálázás)."""
    import os
    import socket

    from core.kernel.config.config_loader import settings

    raw = (getattr(settings, "platform_event_outbox_worker_instance_id", "") or "").strip()
    if raw:
        return raw
    return f"{socket.gethostname()}:{os.getpid()}"


def _instance_role_value() -> str | None:
    try:
        return get_instance_role().value
    except Exception:
        return None


class OutboxWorker:
    """Outbox tábla poller és esemény dispatcher.

    Teljesen függetlenített a web-process runtime-jától:
    nincs FastAPI, nincs middleware, nincs request context függőség.
    """

    def __init__(
        self,
        outbox_repository: "PlatformEventOutboxRepository",
        dispatcher: "EventDispatcher",
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SEC,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay_seconds: int = DEFAULT_RETRY_DELAY_SEC,
        batch_size: int = DEFAULT_BATCH_SIZE,
        stale_lock_after_sec: int = 300,
        handler_timeout_seconds: int = 15,
        lock_owner: str | None = None,
    ) -> None:
        self._outbox = outbox_repository
        self._dispatcher = dispatcher
        self._poll_interval = max(0.1, float(poll_interval_seconds))
        self._max_retries = max_retries
        self._retry_delay = retry_delay_seconds
        self._batch_size = batch_size
        self._stale_lock_after_sec = max(1, int(stale_lock_after_sec))
        self._handler_timeout_seconds = max(1, int(handler_timeout_seconds))
        self._lock_owner = lock_owner
        self._worker_run_id = uuid.uuid4().hex
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Állapot lekérdezők
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        """True, ha a háttérszál fut és nem áll le."""
        return (
            self._thread is not None
            and self._thread.is_alive()
            and not self._stop.is_set()
        )

    def status(self) -> str:
        """Szöveges állapot (életciklus monitorozáshoz)."""
        if self._thread is None:
            return "not_started"
        if self._thread.is_alive():
            return "running" if not self._stop.is_set() else "stopping"
        return "stopped"

    # ------------------------------------------------------------------
    # Indítás / leállítás
    # ------------------------------------------------------------------

    def start_thread(self) -> None:
        """Háttérszálként indítja a worker loop-ot (combined/dev mód).

        Ha már fut, nem indít új szálat.
        FONTOS: web-only processben NE hívd – ott a worker process felelős.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name="outbox-worker",
        )
        self._thread.start()
        log_structured_event(
            "core.outbox_worker",
            "outbox_worker.started",
            mode="thread",
            worker_run_id=self._worker_run_id,
            worker_role="thread",
            lock_owner=self._lock_owner,
        )

    def run_blocking(self) -> None:
        """Az aktuális szálban futtatja a worker loop-ot (standalone process mód).

        SIGTERM / SIGINT hatására a _stop event-et beállítva leáll.
        """
        log_structured_event(
            "core.outbox_worker",
            "outbox_worker.started",
            mode="blocking",
            worker_run_id=self._worker_run_id,
            worker_role="worker",
            lock_owner=self._lock_owner,
        )
        self._stop.clear()
        self._poll_loop()

    def stop(self, timeout: float = 5.0) -> None:
        """Leállítja a háttérszálat és megvárja a befejezést."""
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                log_structured_event(
                    "core.outbox_worker",
                    "outbox_worker.stop_timeout",
                    level=logging.WARNING,
                    timeout_sec=timeout,
                    worker_run_id=self._worker_run_id,
                    lock_owner=self._lock_owner,
                )
        log_structured_event(
            "core.outbox_worker",
            "outbox_worker.stopped",
            worker_run_id=self._worker_run_id,
            lock_owner=self._lock_owner,
        )

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        """Főciklus: eseményeket kérdez le és dispatxhol, amíg le nem állítják."""
        while not self._stop.is_set():
            try:
                processed = self._process_batch()
                if processed == 0:
                    # Nincs feldolgozandó esemény → várakozás
                    self._stop.wait(self._poll_interval)
            except Exception as exc:
                log_exception_event(
                    "core.outbox_worker",
                    "outbox_worker.poll_loop_failed",
                    exc,
                    worker_run_id=self._worker_run_id,
                    worker_role="worker",
                    lock_owner=self._lock_owner,
                )
                self._stop.wait(self._poll_interval)

    def _process_batch(self) -> int:
        """Lefoglalja és feldolgozza egy adag eseményt. Visszaadja a feldolgozottak számát."""
        batch_id = uuid.uuid4().hex
        items = self._outbox.claim_next_batch(
            limit=self._batch_size,
            stale_lock_after_sec=self._stale_lock_after_sec,
            lock_owner=self._lock_owner,
        )
        if items:
            increment_metric("platform.outbox.batch.count", 1.0)
            increment_metric("platform.outbox.claimed.count", float(len(items)), tags={"lock_owner": self._lock_owner})
            log_structured_event(
                "core.outbox_worker",
                "outbox_worker.batch_claimed",
                batch_id=batch_id,
                claimed_count=len(items),
                stale_lock_after_sec=self._stale_lock_after_sec,
                worker_run_id=self._worker_run_id,
                worker_role="worker",
                lock_owner=self._lock_owner,
            )
        for item in items:
            self._process_one(item, batch_id=batch_id)
        return len(items)

    def _process_one(self, item: "OutboxWorkItem", *, batch_id: str) -> None:
        meta = dict((item.payload or {}).get("_meta") or {})
        with observability_scope(
            correlation_id=meta.get("correlation_id"),
            request_id=meta.get("request_id"),
            tenant_id=meta.get("tenant_id"),
            tenant_slug=meta.get("tenant_slug"),
            user_id=meta.get("user_id"),
            event_name=item.event_type,
            worker_run_id=self._worker_run_id,
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
                batch_id=batch_id,
                lock_owner=self._lock_owner,
            )
            try:
                self._dispatch_with_timeout(item.event_type, item.payload or {})
                self._outbox.mark_processed(item.id)
                increment_metric("platform.outbox.processed.count", 1.0, tags={"event_type": item.event_type})
                log_structured_event(
                    "core.outbox_worker",
                    "outbox_worker.event_processed",
                    event_id=item.id,
                    event_type=item.event_type,
                    retry_count=item.attempts,
                    batch_id=batch_id,
                    lock_owner=self._lock_owner,
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
                    batch_id=batch_id,
                    lock_owner=self._lock_owner,
                    outcome="failure",
                )
                self._outbox.mark_failed(
                    item.id,
                    error=str(exc),
                    max_attempts=self._max_retries,
                    retry_delay_seconds=self._retry_delay,
                )

    def _dispatch_with_timeout(self, event_type: str, payload: dict) -> None:
        error_holder: list[Exception] = []

        def _target() -> None:
            try:
                self._dispatcher.dispatch(event_type, payload)
            except Exception as exc:  # pragma: no cover - propagated below
                error_holder.append(exc)

        thread = threading.Thread(target=_target, daemon=True, name=f"outbox-dispatch-{event_type}")
        thread.start()
        thread.join(timeout=float(self._handler_timeout_seconds))
        if thread.is_alive():
            increment_metric("outbox.handler_timeout_total", 1.0, tags={"event_type": event_type})
            raise TimeoutError(
                f"Outbox handler timeout ({self._handler_timeout_seconds}s) event_type={event_type}"
            )
        if error_holder:
            raise error_holder[0]


__all__ = [
    "OutboxWorker",
    "DEFAULT_POLL_INTERVAL_SEC",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY_SEC",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_STALE_LOCK_SEC",
    "default_outbox_lock_owner",
]
