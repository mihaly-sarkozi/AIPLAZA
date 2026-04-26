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

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.extensions.tenant.context.tenant_context import current_tenant_schema
from core.kernel.logging.observability import (
    get_observability_context,
    increment_metric,
    log_exception_event,
    log_structured_event,
)
from core.kernel.config.instance_role import get_instance_role
from core.platform.events.outbox import PlatformEventOutboxRepository


class EventDeliveryError(RuntimeError):
    """Outbox enqueue hiba esetén dobódik."""


# ---------------------------------------------------------------------------
# Proxy wrapper-ek (request path-ban hívódnak, outbox-ba írnak)
# ---------------------------------------------------------------------------


class SecurityLoggerProxy:
    """Security logger proxy: method hívásokat outbox-ba ír."""

    def __init__(self, publisher: "SecurityAuditEventChannel") -> None:
        self._publisher = publisher

    def __getattr__(self, name: str) -> Any:
        def _send(*args: Any, **kwargs: Any) -> None:
            self._publisher.publish(
                "security",
                {"method": name, "args": list(args), "kwargs": kwargs},
            )
        return _send


class AuditServiceProxy:
    """Audit service proxy: log() hívásokat outbox-ba ír tenant kontextussal."""

    def __init__(self, publisher: "SecurityAuditEventChannel") -> None:
        self._publisher = publisher

    def log(
        self,
        action: AuditLogAction,
        *,
        user_id: int | None = None,
        actor_type: str | None = None,
        event_name: str | None = None,
        outcome: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        tenant_slug: Optional[str] = None,
    ) -> None:
        slug = tenant_slug if tenant_slug is not None else current_tenant_schema.get(None)
        self._publisher.publish(
            "audit",
            {
                "action": str(action),
                "user_id": user_id,
                "actor_type": actor_type,
                "event_name": event_name,
                "outcome": outcome,
                "target_type": target_type,
                "target_id": target_id,
                "correlation_id": correlation_id,
                "details": details,
                "ip": ip,
                "user_agent": user_agent,
                "tenant_slug": slug,
            },
        )


class EmailServiceProxy:
    """Email service proxy: email küldési hívásokat outbox-ba ír."""

    def __init__(self, publisher: "SecurityAuditEventChannel", email_service: Any) -> None:
        self._publisher = publisher
        self._email_service = email_service

    def send_2fa_code(
        self,
        to_email: str,
        code: str,
        pending_token: Optional[str] = None,
        lang: Optional[str] = None,
        expiry_minutes: int = 10,
    ) -> bool:
        self._publisher.publish(
            "email_2fa",
            {
                "to_email": to_email,
                "code": code,
                "pending_token": pending_token,
                "lang": lang,
                "expiry_minutes": expiry_minutes,
            },
        )
        return True

    def send_set_password_invite(
        self,
        to_email: str,
        set_password_link: str,
        lang: str | None = None,
    ) -> bool:
        self._publisher.publish(
            "email_invite",
            {
                "to_email": to_email,
                "set_password_link": set_password_link,
                "lang": lang,
            },
        )
        return True

    def __getattr__(self, name: str) -> Any:
        return getattr(self._email_service, name)


# ---------------------------------------------------------------------------
# Fő publisher osztály
# ---------------------------------------------------------------------------


class SecurityAuditEventChannel:
    """Biztonsági audit esemény csatorna – kizárólag publisher funkció.

    A worker szál / worker process kezeléséhez az OutboxWorker-t használd
    (core.platform.events.worker). Az event_channel feladata csak az, hogy
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
        enriched_payload = dict(payload or {})
        meta = dict(enriched_payload.get("_meta") or {})
        current_context = get_observability_context()
        meta.setdefault("correlation_id", current_context.get("correlation_id"))
        meta.setdefault("request_id", current_context.get("request_id"))
        meta.setdefault("tenant_id", current_context.get("tenant_id"))
        meta.setdefault("tenant_slug", current_context.get("tenant_slug") or current_tenant_schema.get(None))
        meta.setdefault("user_id", current_context.get("user_id"))
        meta.setdefault("event_name", event_type)
        try:
            meta.setdefault("instance_role", get_instance_role().value)
        except Exception:
            meta.setdefault("instance_role", None)
        enriched_payload["_meta"] = meta
        try:
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
