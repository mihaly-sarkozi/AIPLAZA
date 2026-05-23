# backend/core/kernel/runtime/module_registration.py
# Feladat: Az AppContainer runtime modulregisztrációs lépését fogja össze. A manifest modulokat az infrastructure és security registrykkel regisztrálja, és kezdeti lifecycle state-ként átadja az outbox worker referenciát. Core runtime wiring, amely a bootstrap modulregisztrációt az app assemblybe illeszti.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
from core.kernel.bootstrap.modules import ModuleRegistry, register_manifest_modules
from core.kernel.bootstrap.security import SecurityRegistry
from core.kernel.events.worker import OutboxWorker
from core.kernel.app.app_manifest import AppManifest


def register_modules(
    *,
    infrastructure: InfrastructureRegistry,
    security: SecurityRegistry,
    manifest: AppManifest,
    outbox_worker: OutboxWorker | None,
) -> ModuleRegistry:
    """Kétfázisú platform -> app modul regisztráció lifecycle state-tel (outbox_worker)."""
    return register_manifest_modules(
        infra=infrastructure,
        security=security,
        audit_service=security.audit_service,
        manifest=manifest,
        initial_state={"outbox_worker": outbox_worker},
    )

