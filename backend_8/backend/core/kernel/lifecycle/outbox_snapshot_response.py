from __future__ import annotations

from pydantic import BaseModel


class OutboxSnapshotResponse(BaseModel):
    pending: int = 0
    running: int = 0
    failed: int = 0
    dead_letter: int = 0
    stuck_leases: int = 0
    oldest_pending_seconds: float = 0.0
    average_attempts: float = 0.0
    worker_status: str = "unknown"
    worker_heartbeat_at: str | None = None
    worker_heartbeat_age_seconds: float | None = None
