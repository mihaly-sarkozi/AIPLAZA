# backend/core/kernel/runtime/runtime_lifecycle.py
# Feladat: Runtime storage inicializálást és háttérszolgáltatások életciklusát koordinálja. Létrehozza/ellenőrzi az outbox storage-t, többpéldányos auth guardokat futtat, combined módban elindítja az embedded outbox workert, shutdownkor pedig leállítja. Core runtime lifecycle controller az AppContainer számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.runtime.instance_role import should_run_background_workers
from core.kernel.bootstrap.infrastructure_registry import InfrastructureRegistry
from core.kernel.events.outbox import ensure_platform_event_outbox
from core.modules.tenant.models.tenant_orm import TenantORM
from core.kernel.events.worker import OutboxWorker


class RuntimeLifecycleController:
    """Háttér-folyamatok és perzisztencia-inicializálás koordinálása."""

    def __init__(
        self,
        *,
        infrastructure: InfrastructureRegistry,
        outbox_worker: OutboxWorker | None,
    ) -> None:
        self._infrastructure = infrastructure
        self._outbox_worker = outbox_worker

    def initialize_runtime_storage(self) -> None:
        engine = self._infrastructure.db_session_factory.engine
        if engine.dialect.name == "sqlite":
            TenantORM.__table__.create(engine, checkfirst=True)
        else:
            ensure_platform_event_outbox(engine)
        from core.modules.auth.repository.token_allowlist import assert_redis_for_multi_instance as _al_guard
        from core.modules.auth.repository.permissions_changed_store import assert_redis_for_multi_instance as _pc_guard

        _al_guard()
        _pc_guard()

    def start_runtime_services(self) -> None:
        engine = self._infrastructure.db_session_factory.engine
        if engine.dialect.name == "sqlite":
            return
        if self._outbox_worker is not None and should_run_background_workers():
            if not self._outbox_worker.is_running():
                self._outbox_worker.start_thread()

    def outbox_worker_status(self) -> str:
        if self._outbox_worker is None:
            return "disabled"
        return self._outbox_worker.status()

    def shutdown(self) -> None:
        if self._outbox_worker is not None:
            self._outbox_worker.stop()

