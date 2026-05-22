# backend/core/kernel/lifecycle/readiness_response.py
# Feladat: A `/health/ready` endpoint response DTO-ja. Össz readiness státuszt és checkenkénti DB/cache/background worker/startup eredményeket hordoz. Kernel lifecycle readiness web response contract load balancer és release ellenőrzésekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]
