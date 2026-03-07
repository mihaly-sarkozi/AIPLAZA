# apps/core/security/event_channel.py
# Security és audit események aszinkron feldolgozása: queue + háttér worker.
# A service-ek proxykon keresztül logolnak → put a queue-ba → auth válasz gyorsan visszajön;
# a worker külön szálban hívja a valódi SecurityLogger-t és AuditService-t.
# Nagy terhelésnél kisebb latency, nem akad meg az auth flow log/DB írás miatt.
# 2026.02 - Sárközi Mihály

from __future__ import annotations

import logging
import queue
import threading
from typing import Any, Optional

_log = logging.getLogger(__name__)

# Queue max méret: extrém terhelésnél ne nőjön a memória; put block=False vagy put timeout, full esetén drop/warn
DEFAULT_QUEUE_MAXSIZE = 10_000
WORKER_POLL_TIMEOUT_SEC = 1.0


class SecurityLoggerProxy:
    """
    SecurityLogger interface proxy: minden hívás (login_*, logout_*, refresh_*) a queue-ba kerül.
    A worker később meghívja a valódi SecurityLogger megfelelő metódusát.
    """

    def __init__(self, event_queue: queue.Queue) -> None:
        self._queue = event_queue

    def __getattr__(self, name: str) -> Any:
        def _send(*args: Any, **kwargs: Any) -> None:
            try:
                self._queue.put_nowait(
                    {"type": "security", "method": name, "args": args, "kwargs": kwargs}
                )
            except queue.Full:
                _log.warning("event_channel queue full, dropping security event %s", name)

        return _send


class AuditServiceProxy:
    """AuditService.log() proxy: a hívást queue-ba teszi; a worker írja a DB-be."""

    def __init__(self, event_queue: queue.Queue) -> None:
        self._queue = event_queue

    def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        try:
            self._queue.put_nowait(
                {
                    "type": "audit",
                    "action": action,
                    "user_id": user_id,
                    "details": details,
                    "ip": ip,
                    "user_agent": user_agent,
                }
            )
        except queue.Full:
            _log.warning("event_channel queue full, dropping audit event %s", action)


class SecurityAuditEventChannel:
    """
    Központi eseménycsatorna: security + audit + email (2FA) események queue-ba kerülnek,
    egy háttérszál feldolgozza (valódi SecurityLogger + AuditService + EmailService).
    Login step1 nem vár SMTP-re: 2FA kód email háttérben megy.
    """

    def __init__(
        self,
        security_logger: Any,
        audit_service: Any,
        email_service: Any,
        *,
        queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE,
    ) -> None:
        self._security_logger = security_logger
        self._audit_service = audit_service
        self._email_service = email_service
        self._queue: queue.Queue = queue.Queue(maxsize=queue_maxsize)
        self._worker_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

        self.security_logger = SecurityLoggerProxy(self._queue)
        self.audit_service = AuditServiceProxy(self._queue)

    def enqueue_email_2fa(
        self,
        to_email: str,
        code: str,
        pending_token: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> None:
        """2FA kód email háttérbe (login step1 ne várjon SMTP-re)."""
        try:
            self._queue.put_nowait(
                {
                    "type": "email_2fa",
                    "to_email": to_email,
                    "code": code,
                    "pending_token": pending_token,
                    "lang": lang,
                }
            )
        except queue.Full:
            _log.warning("event_channel queue full, dropping email_2fa event")

    def start_worker(self) -> None:
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return
        self._stop.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=False)
        self._worker_thread.start()
        _log.info("SecurityAuditEventChannel worker started")

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=WORKER_POLL_TIMEOUT_SEC)
            except queue.Empty:
                continue
            try:
                if event.get("type") == "security":
                    method = event.get("method")
                    args = event.get("args", ())
                    kwargs = event.get("kwargs", {})
                    if method and hasattr(self._security_logger, method):
                        getattr(self._security_logger, method)(*args, **kwargs)
                elif event.get("type") == "audit":
                    from apps.audit.sanitization import sanitize_details
                    details = sanitize_details(event.get("details"))
                    self._audit_service.log(
                        action=event["action"],
                        user_id=event.get("user_id"),
                        details=details,
                        ip=event.get("ip"),
                        user_agent=event.get("user_agent"),
                    )
                elif event.get("type") == "email_2fa":
                    self._email_service.send_2fa_code(
                        event.get("to_email", ""),
                        event.get("code", ""),
                        pending_token=event.get("pending_token"),
                        lang=event.get("lang"),
                    )
            except Exception as e:
                _log.exception("event_channel worker error processing event: %s", e)

    def stop(self) -> None:
        self._stop.set()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                _log.warning("event_channel worker did not stop within 5s")
            self._worker_thread = None
        _log.info("SecurityAuditEventChannel worker stopped")
