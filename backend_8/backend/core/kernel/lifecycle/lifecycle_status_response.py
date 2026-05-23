# backend/core/kernel/lifecycle/lifecycle_status_response.py
# Feladat: A `/platform/lifecycle` endpoint részletes runtime státusz DTO-ja. Readiness checkeket, startup/shutdown időpontokat, futásszámlálókat, utolsó hibákat és startup-in-progress állapotot ad vissza diagnosztikai célra. Kernel lifecycle admin/ops web response contract.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel


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
