# backend/core/kernel/events/worker.py
# Feladat: Az OutboxWorker osztály életciklusát adja thread és blocking futtatási módban. Állapotot, konfigurációt és indítás/leállítás API-t kezel, a tényleges polling és feldolgozó logikát a worker_loop.py-ra delegálja. Core worker komponens, amely webtől függetlenül futtatható.
# Sárközi Mihály - 2026.05.21

"""Outbox worker – önállóan futtatható esemény-feldolgozó.

Ez a modul biztosítja az OutboxWorker osztályt, amely kétféleképpen futtatható:

  1. Szálként (thread mód) – fejlesztői combined módban:
        worker.start_thread()   # háttérszálat indít
        worker.stop()           # jelzi a leállást, megvárja a szálat

  2. Blokkoló módban (standalone process) – skálázott deploymentben:
        worker.run_blocking()   # az aktuális szálban fut, SIGTERM/SIGINT-ra megáll

Skálázott deploymentben (INSTANCE_ROLE=worker):
    INSTANCE_ROLE=worker python -m core.kernel.events

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

from core.kernel.logging.observability import (
    log_structured_event,
)
from core.kernel.events.worker_loop import process_batch, process_one, run_poll_loop

if TYPE_CHECKING:
    from core.kernel.events.dispatcher import EventDispatcher
    from core.kernel.events.outbox import PlatformEventOutboxRepository, OutboxWorkItem

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
        lease_seconds: int = 300,
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
        self._lease_seconds = max(1, int(lease_seconds))
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

    @property
    def outbox(self) -> "PlatformEventOutboxRepository":
        return self._outbox

    @property
    def dispatcher(self) -> "EventDispatcher":
        return self._dispatcher

    @property
    def poll_interval(self) -> float:
        return self._poll_interval

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def retry_delay_seconds(self) -> int:
        return self._retry_delay

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def stale_lock_after_sec(self) -> int:
        return self._stale_lock_after_sec

    @property
    def handler_timeout_seconds(self) -> int:
        return self._handler_timeout_seconds

    @property
    def lease_seconds(self) -> int:
        return self._lease_seconds

    @property
    def lock_owner(self) -> str | None:
        return self._lock_owner

    @property
    def worker_run_id(self) -> str:
        return self._worker_run_id

    @property
    def stop_event(self) -> threading.Event:
        return self._stop

    def _poll_loop(self) -> None:
        run_poll_loop(self)

    def _process_batch(self) -> int:
        return process_batch(self)

    def _process_one(self, item: "OutboxWorkItem", *, batch_id: str) -> None:
        process_one(self, item, batch_id=batch_id)


__all__ = [
    "OutboxWorker",
    "DEFAULT_POLL_INTERVAL_SEC",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_RETRY_DELAY_SEC",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_STALE_LOCK_SEC",
    "default_outbox_lock_owner",
]
