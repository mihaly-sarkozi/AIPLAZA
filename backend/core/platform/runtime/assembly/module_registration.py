"""Modul regisztráció: infrastruktúra + security + manifest → ModuleRegistry."""
from __future__ import annotations

from core.platform.bootstrap.infrastructure import InfrastructureRegistry
from core.platform.bootstrap.modules import ModuleRegistry, register_manifest_modules
from core.platform.bootstrap.security import SecurityRegistry
from core.platform.events.worker import OutboxWorker
from core.platform.manifest import PlatformManifest


def register_modules(
    *,
    infrastructure: InfrastructureRegistry,
    security: SecurityRegistry,
    manifest: PlatformManifest,
    outbox_worker: OutboxWorker | None,
) -> ModuleRegistry:
    """Kétfázisú platform → app modul regisztráció lifecycle state-tel (outbox_worker)."""
    return register_manifest_modules(
        infra=infrastructure,
        security=security,
        audit_service=security.audit_service,
        manifest=manifest,
        initial_state={"outbox_worker": outbox_worker},
    )
