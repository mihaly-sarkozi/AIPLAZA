# backend/core/kernel/lifecycle/health_response.py
# Feladat: A `/health` endpoint összetett response DTO-ja. Az összállapot mellett beágyazza a liveness és readiness válaszokat, így load balancer és diagnosztikai kliensek egyetlen hívásból látják a process és függőségek állapotát. Kernel lifecycle web response contract.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel

from core.kernel.lifecycle.liveness_response import LivenessResponse
from core.kernel.lifecycle.readiness_response import ReadinessResponse


class HealthResponse(BaseModel):
    status: str
    liveness: LivenessResponse
    readiness: ReadinessResponse
