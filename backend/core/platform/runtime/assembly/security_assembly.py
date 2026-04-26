"""Biztonsági réteg összeállítás: nyers audit service, outbox repo, SecurityRegistry.

A SecurityRegistry tartalmazza a TokenService-t, az opcionális event channelt,
az EventDispatcher-t, valamint a (esetleg proxyzott) audit/email service referenciákat.
Az OutboxWorker indítása nem része – lásd ``outbox_wiring`` + ``runtime_lifecycle``.
"""
from __future__ import annotations

from core.capabilities.audit.service.audit_service import AuditService
from core.kernel.clock import Clock
from core.platform.bootstrap.infrastructure import InfrastructureRegistry
from core.platform.bootstrap.security import SecurityRegistry, build_security
from core.platform.events.outbox import PlatformEventOutboxRepository


def assemble_security_layer(
    *,
    infrastructure: InfrastructureRegistry,
    clock: Clock,
) -> tuple[AuditService, PlatformEventOutboxRepository, SecurityRegistry]:
    """AuditService (nyers), PlatformEventOutboxRepository és SecurityRegistry felépítése.

    Returns:
        (audit_service_raw, event_outbox_repo, security_registry)

    Megjegyzés: a ``register_manifest_modules``-nak a ``security.audit_service``-t kell
    átadni (proxy), míg a kernel DI-hez a nyers ``AuditService`` példány kell.
    """
    audit_service = AuditService(infrastructure.repositories.audit_repo)
    event_outbox_repo = PlatformEventOutboxRepository(infrastructure.db_session_factory)
    security = build_security(
        audit_service=audit_service,
        email_service=infrastructure.email_service,
        outbox_repository=event_outbox_repo,
        clock=clock,
    )
    return audit_service, event_outbox_repo, security
