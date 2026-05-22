# backend/core/kernel/lifecycle/lifecycle_service.py
# Feladat: A lifecycle application service-t valósítja meg. Startup/shutdown eseményekkel frissíti a runtime állapotot, DB/cache/Redis/object storage/migration/background worker probe-okból readiness választ épít, és health/liveness/runtime status DTO-kat állít elő. Kernel service a lifecycle router és probe repository között.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from typing import TYPE_CHECKING

from core.kernel.config.environment import is_deployed_env, normalize_app_env
from core.kernel.runtime.clock import utc_now
from core.kernel.lifecycle.lifecycle_readiness_policy import LifecycleReadinessPolicy
from core.kernel.lifecycle.lifecycle_state import LifecycleState
from core.kernel.lifecycle.health_response import HealthResponse
from core.kernel.lifecycle.lifecycle_status_response import LifecycleStatusResponse
from core.kernel.lifecycle.liveness_response import LivenessResponse
from core.kernel.lifecycle.outbox_snapshot_response import OutboxSnapshotResponse
from core.kernel.lifecycle.readiness_response import ReadinessResponse

if TYPE_CHECKING:
    from core.kernel.lifecycle.lifecycle_probe_repository import LifecycleProbeRepository


class LifecycleService:
    def __init__(
        self,
        *,
        probe_repository: LifecycleProbeRepository,
        readiness_policy: LifecycleReadinessPolicy | None = None,
        state: LifecycleState | None = None,
    ):
        self._state = state or LifecycleState()
        self._probes = probe_repository
        self._readiness_policy = readiness_policy or LifecycleReadinessPolicy()

    def mark_startup_begin(self) -> None:
        self._state.started_at = utc_now()
        self._state.startup_runs += 1
        self._state.last_startup_error = None
        self._state.startup_in_progress = True

    def mark_startup_complete(self) -> None:
        self._state.startup_completed_at = utc_now()
        self._state.startup_in_progress = False

    def mark_startup_error(self, error: Exception) -> None:
        self._state.last_startup_error = str(error)
        self._state.startup_in_progress = False

    def mark_shutdown_begin(self) -> None:
        self._state.shutdown_started_at = utc_now()
        self._state.shutdown_runs += 1
        self._state.last_shutdown_error = None

    def mark_shutdown_error(self, error: Exception) -> None:
        self._state.last_shutdown_error = str(error)

    def health(self) -> HealthResponse:
        readiness = self.readiness()
        return HealthResponse(
            status="ok" if readiness.status == "ready" else "degraded",
            liveness=self.liveness(),
            readiness=readiness,
        )

    def liveness(self) -> LivenessResponse:
        return LivenessResponse(
            status="alive",
            started_at=self._state.started_at.isoformat() if self._state.started_at else None,
            startup_completed=bool(self._state.startup_completed_at),
        )

    def readiness(self) -> ReadinessResponse:
        checks: dict[str, str] = {}
        critical_failures: list[str] = []
        deployed_env = is_deployed_env(normalize_app_env())
        startup_status, startup_complete = self._readiness_policy.startup_check(self._state)
        ready = startup_complete
        checks["startup"] = startup_status

        try:
            checks["db"] = self._probes.check_database()
        except Exception as exc:
            ready = False
            checks["db"] = f"error:{exc}"
            critical_failures.append("db")

        try:
            checks["cache"] = self._probes.check_cache()
        except Exception as exc:
            ready = False
            checks["cache"] = f"error:{exc}"

        try:
            checks["redis"] = self._probes.check_redis()
        except Exception as exc:
            ready = False
            checks["redis"] = f"error:{exc}"
            if deployed_env:
                critical_failures.append("redis")

        try:
            checks["object_storage"] = self._probes.check_object_storage()
        except Exception as exc:
            ready = False
            checks["object_storage"] = f"error:{exc}"
            if deployed_env:
                critical_failures.append("object_storage")

        try:
            checks["migrations"] = self._probes.check_migrations()
        except Exception as exc:
            ready = False
            checks["migrations"] = f"error:{exc}"
            critical_failures.append("migrations")

        try:
            checks["url_ingest_isolation"] = self._probes.check_url_ingest_isolation_guard()
        except Exception as exc:
            ready = False
            checks["url_ingest_isolation"] = f"error:{exc}"
            critical_failures.append("url_ingest_isolation")

        try:
            worker_status = self._probes.check_background_worker()
            checks["outbox_worker"] = worker_status
            if not self._readiness_policy.background_worker_ready(worker_status):
                ready = False
        except Exception as exc:
            ready = False
            checks["outbox_worker"] = f"error:{exc}"

        try:
            checks["outbox"] = self._probes.check_outbox_queue()
        except Exception as exc:
            ready = False
            checks["outbox"] = f"error:{exc}"
            critical_failures.append("outbox")

        try:
            checks["smtp"] = self._probes.check_smtp()
        except Exception as exc:
            ready = False
            checks["smtp"] = f"error:{exc}"
            critical_failures.append("smtp")

        self._state.checks = checks
        if not startup_complete:
            status = "not_ready"
        elif critical_failures:
            status = "degraded"
        elif ready:
            status = "ready"
        else:
            status = "not_ready"
        return ReadinessResponse(status=status, checks=checks)

    def runtime_status(self) -> LifecycleStatusResponse:
        readiness = self.readiness()
        return LifecycleStatusResponse(
            status=readiness.status,
            checks=readiness.checks,
            started_at=self._state.started_at.isoformat() if self._state.started_at else None,
            startup_completed_at=self._state.startup_completed_at.isoformat() if self._state.startup_completed_at else None,
            shutdown_started_at=self._state.shutdown_started_at.isoformat() if self._state.shutdown_started_at else None,
            startup_runs=self._state.startup_runs,
            shutdown_runs=self._state.shutdown_runs,
            last_startup_error=self._state.last_startup_error,
            last_shutdown_error=self._state.last_shutdown_error,
            startup_in_progress=self._state.startup_in_progress,
        )

    def outbox_snapshot(self) -> OutboxSnapshotResponse:
        raw = self._probes.outbox_queue_snapshot()
        return OutboxSnapshotResponse(
            pending=int(raw.get("pending") or 0),
            running=int(raw.get("running") or 0),
            failed=int(raw.get("failed") or 0),
            dead_letter=int(raw.get("dead_letter") or 0),
            stuck_leases=int(raw.get("stuck_leases") or 0),
            oldest_pending_seconds=float(raw.get("oldest_pending_seconds") or 0.0),
            average_attempts=float(raw.get("average_attempts") or 0.0),
            worker_status=str(raw.get("worker_status") or "unknown"),
            worker_heartbeat_at=(
                str(raw.get("worker_heartbeat_at"))
                if raw.get("worker_heartbeat_at") is not None
                else None
            ),
            worker_heartbeat_age_seconds=(
                float(raw.get("worker_heartbeat_age_seconds"))
                if raw.get("worker_heartbeat_age_seconds") is not None
                else None
            ),
        )
