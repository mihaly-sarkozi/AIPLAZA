from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LifecycleState:
    started_at: datetime | None = None
    startup_completed_at: datetime | None = None
    shutdown_started_at: datetime | None = None
    startup_runs: int = 0
    shutdown_runs: int = 0
    last_startup_error: str | None = None
    last_shutdown_error: str | None = None
    checks: dict[str, str] = field(default_factory=dict)
    startup_in_progress: bool = False
