# backend/core/kernel/events/event_channel.py
# Feladat: Request pathból nem blokkoló outbox publish réteget ad security, audit és email eseményekhez. Proxy service-eket biztosít, payloadot gazdagít, backlog limitet ellenőriz, majd az eseményt a perzisztens outbox repositoryba írja. A security bootstrap építi fel, ezért core event publisher adapter.
# Sárközi Mihály - 2026.05.21

"""Biztonsági audit esemény csatorna – publisher szint.

Felelősség: proxy wrapper-ek biztosítása az audit/security/email service-ekhez,
amelyek a kérés kontextusában hívódnak, és az eseményeket az outbox-ba írják
(nem blokkoló, nem szinkron delivery).

A tényleges feldolgozást (outbox polling, event dispatch, retry) az
OutboxWorker végzi – az a web-processztől elkülönítetten futtatható
(önálló worker-folyamatban INSTANCE_ROLE=worker esetén, vagy szálként
fejlesztői combined módban).

Architekturális szétválasztás (több példány / worker kompatibilis):
  event_channel.py (ez) → KÉRÉS PATH: csak outbox-ba ír (append / idempotency_key)
  outbox.py             → Perzisztens sor + claim_next_batch (SKIP LOCKED, lock, retry)
  worker.py             → HÁTTÉR: külön process vagy combined szál, dispatch + mark_*
  dispatcher.py         → ROUTOLÁS: event_type → handler(ok)
  handlers.py           → HANDLER-EK: idempotens delivery logika
"""
from __future__ import annotations

from typing import Any, Optional

from core.kernel.logging.observability import (
    increment_metric,
    observe_metric,
    log_exception_event,
    log_structured_event,
)
from core.kernel.config.config_loader import settings
from core.kernel.events.outbox import PlatformEventOutboxRepository
from core.kernel.events.event_payload import enrich_event_payload
from core.kernel.events.event_proxies import (
    AuditServiceProxy,
    EmailServiceProxy,
    SecurityLoggerProxy,
)


class EventDeliveryError(RuntimeError):
    """Outbox enqueue hiba esetén dobódik."""


# ---------------------------------------------------------------------------
# Fő publisher osztály
# ---------------------------------------------------------------------------


class SecurityAuditEventChannel:
    """Biztonsági audit esemény csatorna – kizárólag publisher funkció.

    A worker szál / worker process kezeléséhez az OutboxWorker-t használd
    (core.kernel.events.worker). Az event_channel feladata csak az, hogy
    a request path-ban az audit/security/email hívásokat non-blokkló módon
    az outbox-ba írja.

    Backward-compat megjegyzés:
      A régi start_worker() / stop() / is_worker_running() API el lett távolítva.
      A worker életciklus az AppContainer-ben OutboxWorker példányon keresztül kezelt.
    """

    def __init__(
        self,
        security_logger: Any,
        audit_service: Any,
        email_service: Any,
        *,
        outbox_repository: PlatformEventOutboxRepository,
        # Alábbi paraméterek az OutboxWorker-ben vannak, itt visszafelé-kompatibilitásból maradtak
        max_retries: int = 10,
        retry_delay_seconds: int = 5,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._security_logger = security_logger
        self._audit_service = audit_service
        self._email_service = email_service
        self._outbox = outbox_repository

        # Worker paraméterek megőrzése (OutboxWorker számára adhatók át)
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.poll_interval_seconds = poll_interval_seconds

        self.security_logger = SecurityLoggerProxy(self)
        self.audit_service = AuditServiceProxy(self)
        self.email_service = EmailServiceProxy(self, email_service)

    def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> None:
        """Eseményt ír az outbox táblába (non-blokkoló, a worker dolgozza fel).

        FONTOS: NEM indít háttérszálat. A feldolgozásért az OutboxWorker felel.
        ``idempotency_key``: ugyanazzal a kulccsal többszöri publish nem hoz létre duplikát sort.
        """
        enriched_payload = enrich_event_payload(event_type, payload)
        meta = dict(enriched_payload.get("_meta") or {})
        backlog_soft_limit = max(1, int(getattr(settings, "platform_event_outbox_backlog_soft_limit", 5000) or 5000))
        try:
            backlog_size = int(self._outbox.backlog_size()) if hasattr(self._outbox, "backlog_size") else 0
            observe_metric("outbox.backlog_size", float(backlog_size), unit="count")
            if backlog_size >= backlog_soft_limit:
                increment_metric("outbox.publish_rejected_total", 1.0, tags={"reason": "backlog_soft_limit"})
                raise EventDeliveryError(
                    f"Outbox backlog limit reached ({backlog_size}/{backlog_soft_limit})."
                )
            self._outbox.append(
                event_type=event_type,
                payload=enriched_payload,
                idempotency_key=idempotency_key,
            )
            increment_metric("platform.outbox.queued.count", 1.0, tags={"event_type": event_type})
            log_structured_event(
                "core.event_channel",
                "outbox.event.queued",
                event_type=event_type,
                idempotency_key=idempotency_key,
                tenant_id=meta.get("tenant_id"),
                tenant_slug=meta.get("tenant_slug"),
                user_id=meta.get("user_id"),
                request_id=meta.get("request_id"),
            )
        except Exception as exc:
            log_exception_event(
                "core.event_channel",
                "outbox.event.enqueue_failed",
                exc,
                event_type=event_type,
                idempotency_key=idempotency_key,
                tenant_id=meta.get("tenant_id"),
                tenant_slug=meta.get("tenant_slug"),
                user_id=meta.get("user_id"),
                request_id=meta.get("request_id"),
            )
            raise EventDeliveryError(
                f"Esemény outbox-ba írása sikertelen: {event_type}"
            ) from exc

    def enqueue_email_2fa(
        self,
        to_email: str,
        code: str,
        pending_token: Optional[str] = None,
        lang: Optional[str] = None,
    ) -> None:
        """Kényelmi metódus: 2FA email esemény outbox-ba írása."""
        self.publish(
            "email_2fa",
            {
                "to_email": to_email,
                "code": code,
                "pending_token": pending_token,
                "lang": lang,
            },
        )

    def enqueue_email_invite(
        self,
        to_email: str,
        set_password_link: str,
        *,
        lang: Optional[str] = None,
    ) -> None:
        """Kényelmi metódus: meghívó email esemény outbox-ba írása."""
        self.publish(
            "email_invite",
            {
                "to_email": to_email,
                "set_password_link": set_password_link,
                "lang": lang,
            },
        )


__all__ = [
    "AuditServiceProxy",
    "EmailServiceProxy",
    "EventDeliveryError",
    "SecurityAuditEventChannel",
    "SecurityLoggerProxy",
]
