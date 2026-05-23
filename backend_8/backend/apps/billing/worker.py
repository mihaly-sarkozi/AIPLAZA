# backend/apps/billing/worker.py
# Feladat: Billing háttér worker implementáció. Periodikusan lekéri a platform tenant usage service-t és futtatja a due billing ciklusokat, thread alapon, leállítható eventtel. Program-specifikus background feldolgozó.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
import threading

from core.kernel.interface.keys import PLATFORM_TENANT_USAGE_SERVICE
from core.kernel.deps.facade import get_service

DEFAULT_POLL_SECONDS = 3600

logger = logging.getLogger(__name__)


class BillingWorker:
    def __init__(self, poll_seconds: int = DEFAULT_POLL_SECONDS):
        self._poll_seconds = max(60, int(poll_seconds))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                service = get_service(PLATFORM_TENANT_USAGE_SERVICE)
                service.process_due_cycles()
            except Exception:
                logger.exception("Billing background worker cycle failed")
            self._stop.wait(self._poll_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None


__all__ = ["BillingWorker", "DEFAULT_POLL_SECONDS"]
