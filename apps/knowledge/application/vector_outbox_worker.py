from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Optional

_log = logging.getLogger(__name__)


class KnowledgeVectorOutboxWorker:
    """Qdrant outbox retry worker (háttér szál)."""

    def __init__(
        self,
        knowledge_service: Any,
        *,
        poll_interval_sec: float = 5.0,
        batch_limit: int = 50,
    ) -> None:
        self._svc = knowledge_service
        self._poll = max(1.0, float(poll_interval_sec))
        self._batch_limit = max(1, int(batch_limit))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Worker indítása."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=False)
        self._thread.start()
        _log.info("KnowledgeVectorOutboxWorker started")

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                asyncio.run(self._svc.process_vector_outbox(limit=self._batch_limit))
            except Exception as e:
                _log.warning("Vector outbox worker cycle failed: %s", e, exc_info=True)
            self._stop.wait(self._poll)

    def stop(self) -> None:
        """Worker leállítása."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                _log.warning("KnowledgeVectorOutboxWorker did not stop within 5s")
            self._thread = None
        _log.info("KnowledgeVectorOutboxWorker stopped")
