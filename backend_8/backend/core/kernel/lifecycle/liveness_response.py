# backend/core/kernel/lifecycle/liveness_response.py
# Feladat: A `/health/live` endpoint response DTO-ja. A process életjelét, indulási időpontját és startup completion flagjét adja vissza, külső dependency checkek nélkül. Kernel lifecycle liveness web response contract.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: str
    started_at: str | None = None
    startup_completed: bool = False
