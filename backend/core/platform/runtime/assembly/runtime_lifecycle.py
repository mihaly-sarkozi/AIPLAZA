"""Startup / shutdown lifecycle: outbox tábla, Redis guard-ok, háttér worker, leállítás."""
from __future__ import annotations

from core.kernel.config.instance_role import should_run_background_workers
from core.platform.bootstrap.infrastructure import InfrastructureRegistry
from core.platform.events.outbox import ensure_platform_event_outbox
from core.platform.events.worker import OutboxWorker


class RuntimeLifecycleController:
    """Háttér-folyamatok és perzisztencia-inicializálás koordinálása.

    Nem „god object”: csak az outbox tábla, Redis assert-ek és az OutboxWorker
    életciklus tartozik ide; a többi assembly külön modulokban épül fel.
    """

    def __init__(
        self,
        *,
        infrastructure: InfrastructureRegistry,
        outbox_worker: OutboxWorker | None,
    ) -> None:
        self._infrastructure = infrastructure
        self._outbox_worker = outbox_worker

    def initialize_runtime_storage(self) -> None:
        """Outbox tábla létrehozása és horizontális skálázási guard-ok."""
        ensure_platform_event_outbox(self._infrastructure.db_session_factory.engine)
        from core.platform.auth.token_allowlist import assert_redis_for_multi_instance as _al_guard
        from core.platform.auth.permissions_changed_store import assert_redis_for_multi_instance as _pc_guard

        _al_guard()
        _pc_guard()

    def start_runtime_services(self) -> None:
        """OutboxWorker szál indítása csak combined módban (web/worker: nem)."""
        if self._outbox_worker is not None and should_run_background_workers():
            if not self._outbox_worker.is_running():
                self._outbox_worker.start_thread()

    def outbox_worker_status(self) -> str:
        """Lifecycle probe: disabled | running | …"""
        if self._outbox_worker is None:
            return "disabled"
        return self._outbox_worker.status()

    def shutdown(self) -> None:
        """Lifespan shutdown: háttér worker leállítása."""
        if self._outbox_worker is not None:
            self._outbox_worker.stop()
