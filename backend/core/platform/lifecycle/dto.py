from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    liveness: "LivenessResponse"
    readiness: "ReadinessResponse"


class LivenessResponse(BaseModel):
    status: str
    started_at: str | None = None
    startup_completed: bool = False


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


class LifecycleStatusResponse(BaseModel):
    status: str
    checks: dict[str, str]
    started_at: str | None = None
    startup_completed_at: str | None = None
    shutdown_started_at: str | None = None
    startup_runs: int = 0
    shutdown_runs: int = 0
    last_startup_error: str | None = None
    last_shutdown_error: str | None = None
    startup_in_progress: bool = False
