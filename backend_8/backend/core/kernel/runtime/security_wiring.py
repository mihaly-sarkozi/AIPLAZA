# backend/core/kernel/runtime/security_wiring.py
# Feladat: A runtime security layer fő komponenseit állítja össze. AuditService-t, PlatformEventOutboxRepositoryt és SecurityRegistryt épít az infrastructure registryből és clock dependencyből. Core runtime wiring, amely az AppContainer security assembly lépését tartja kicsiben és olvashatóan.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.infrastructure.audit.service.audit_service import AuditService
from core.kernel.runtime.clock import Clock
from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
from core.kernel.bootstrap.security import SecurityRegistry, build_security
from core.kernel.events.outbox import PlatformEventOutboxRepository


def assemble_security_layer(
    *,
    infrastructure: InfrastructureRegistry,
    clock: Clock,
) -> tuple[AuditService, PlatformEventOutboxRepository, SecurityRegistry]:
    """AuditService (nyers), PlatformEventOutboxRepository és SecurityRegistry felépítése."""
    audit_service = AuditService(infrastructure.repositories.audit_repo)
    event_outbox_repo = PlatformEventOutboxRepository(infrastructure.db_session_factory)
    security = build_security(
        audit_service=audit_service,
        email_service=infrastructure.email_service,
        outbox_repository=event_outbox_repo,
        clock=clock,
    )
    return audit_service, event_outbox_repo, security

