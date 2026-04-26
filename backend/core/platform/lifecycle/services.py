from __future__ import annotations

from core.kernel.clock import utc_now
from core.platform.lifecycle.dto import (
    HealthResponse,
    LifecycleStatusResponse,
    LivenessResponse,
    ReadinessResponse,
)
from core.platform.lifecycle.models import LifecycleState
from core.platform.lifecycle.ports import LifecycleProbePort
from core.platform.lifecycle.policies import LifecycleReadinessPolicy


class LifecycleService:
    def __init__(
        self,
        *,
        probe_repository: LifecycleProbePort,
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
        startup_status, startup_complete = self._readiness_policy.startup_check(self._state)
        ready = startup_complete
        checks["startup"] = startup_status

        try:
            checks["database"] = self._probes.check_database()
        except Exception as exc:
            ready = False
            checks["database"] = f"error:{exc}"

        try:
            checks["cache"] = self._probes.check_cache()
        except Exception as exc:
            ready = False
            checks["cache"] = f"error:{exc}"

        try:
            worker_status = self._probes.check_background_worker()
            checks["background_worker"] = worker_status
            if not self._readiness_policy.background_worker_ready(worker_status):
                ready = False
        except Exception as exc:
            ready = False
            checks["background_worker"] = f"error:{exc}"

        self._state.checks = checks
        return ReadinessResponse(status="ready" if ready else "not_ready", checks=checks)

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
