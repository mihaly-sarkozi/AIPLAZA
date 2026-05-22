# backend/core/kernel/events/event_proxies.py
# Feladat: Security logger, audit service és email service proxy osztályokat tartalmaz. Ezek a proxyk a megszokott service hívásokat outbox eseménnyé alakítják, így a request path gyors marad, a tényleges kézbesítést pedig worker dolgozza fel. Az event_channel példányosítja őket, ezért belső core async event adapterek.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any, Optional, TYPE_CHECKING

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.tenant.context.tenant_context import current_tenant_schema

if TYPE_CHECKING:
    from core.kernel.events.event_channel import SecurityAuditEventChannel


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


__all__ = ["AuditServiceProxy", "EmailServiceProxy", "SecurityLoggerProxy"]
