# backend/core/kernel/bootstrap/security.py
# Feladat: Felépíti a kernel biztonsági réteg registryjét. Létrehozza a clockot, token service-t, security loggert, audit/event csatornát és dispatcher handlereket, de nem indít worker folyamatot; azt az AppContainer lifecycle vagy a standalone worker entrypoint kezeli. Core keretrendszer-elem, mert általános security komponenseket köt össze a runtime számára.
# Sárközi Mihály - 2026.05.21

"""Biztonsági réteg bootstrap.

Ez a modul felépíti a SecurityRegistry-t, amely tartalmazza:
  - TokenService (JWT kiadás / validáció)
  - SecurityAuditEventChannel (publisher proxy-k az outbox felé)
  - EventDispatcher + regisztrált handler-ek (OutboxWorker számára)
  - SecurityLogger, AuditService, EmailService (proxyzott változatok)

Az OutboxWorker indítása NEM itt, hanem az AppContainer.start_runtime_services()
metódusában történik, az InstanceRole figyelembevételével:
  - INSTANCE_ROLE=web     → ne indítson worker szálat
  - INSTANCE_ROLE=combined → indítson worker szálat (dev mód)
  - INSTANCE_ROLE=worker  → standalone worker futtatja (nem az AppContainer)
"""
from __future__ import annotations

from dataclasses import dataclass

from core.infrastructure.audit.service.audit_service import AuditService
from core.infrastructure.email.email_service import EmailService
from core.kernel.runtime.clock import Clock, SystemClock
from core.kernel.config.config_loader import settings
from core.kernel.logging.security_logger import SecurityLogger
from core.modules.auth.service.token_service import TokenService
from core.kernel.events.dispatcher import EventDispatcher
from core.kernel.events.event_channel import SecurityAuditEventChannel
from core.kernel.events.handlers import register_security_audit_handlers
from core.kernel.events.outbox import PlatformEventOutboxRepository


@dataclass(frozen=True)
class SecurityRegistry:
    clock: Clock
    token_service: TokenService
    base_security_logger: SecurityLogger
    security_logger: object
    event_channel: SecurityAuditEventChannel | None
    dispatcher: EventDispatcher
    audit_service: object
    email_service: object


def build_security(
    *,
    audit_service: AuditService,
    email_service: EmailService,
    outbox_repository: PlatformEventOutboxRepository,
    clock: Clock | None = None,
) -> SecurityRegistry:
    """Felépíti a biztonsági réteg összes komponensét.

    Az OutboxWorker-t nem indítja el: ``AppContainer`` (combined) vagy külön
    ``python -m core.kernel.events`` worker process.
    """
    effective_clock = clock or SystemClock()
    base_security_logger = SecurityLogger()

    issuer = (getattr(settings, "jwt_issuer", "AIPLAZA") or "AIPLAZA").strip()
    audience = (getattr(settings, "jwt_audience", "") or "").strip()
    token_service = TokenService(
        secret=settings.jwt_secret,
        issuer=issuer or "AIPLAZA",
        audience=audience or None,
        access_exp_min=settings.access_ttl_min,
        refresh_exp_min=settings.refresh_ttl_days * 24 * 60,
        clock=effective_clock,
    )

    # EventDispatcher + handler regisztrálás (outbox → tényleges delivery)
    dispatcher = EventDispatcher()

    event_channel: SecurityAuditEventChannel | None = None
    security_logger: object = base_security_logger
    effective_audit_service: object = audit_service
    effective_email_service: object = email_service

    if getattr(settings, "audit_events_async", True):
        max_retries = max(1, int(getattr(settings, "platform_event_outbox_max_retries", 10)))
        retry_delay = max(1, int(getattr(settings, "platform_event_outbox_retry_delay_sec", 5)))
        poll_interval = max(0.1, float(getattr(settings, "platform_event_outbox_poll_interval_sec", 1.0)))

        event_channel = SecurityAuditEventChannel(
            base_security_logger,
            audit_service,
            email_service,
            outbox_repository=outbox_repository,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay,
            poll_interval_seconds=poll_interval,
        )

        # Handler-ek regisztrálása az EventDispatcher-be (OutboxWorker ebből dispatch-el)
        register_security_audit_handlers(
            dispatcher,
            security_logger=base_security_logger,
            audit_service=audit_service,
            email_service=email_service,
        )

        security_logger = event_channel.security_logger
        effective_audit_service = event_channel.audit_service
        effective_email_service = event_channel.email_service

    return SecurityRegistry(
        clock=effective_clock,
        token_service=token_service,
        base_security_logger=base_security_logger,
        security_logger=security_logger,
        event_channel=event_channel,
        dispatcher=dispatcher,
        audit_service=effective_audit_service,
        email_service=effective_email_service,
    )
