# backend/apps/traffic/schemas/TrafficQuestionUserUsageResponse.py
# Feladat: Felhasználónkénti kérdéshasználat response DTO-ja az aktuális forgalmi időszakra.

from __future__ import annotations

from pydantic import BaseModel


class TrafficQuestionUserUsageResponse(BaseModel):
    """Felhasználónkénti kérdéshasználat az aktuális forgalmi időszakban."""

    user_id: int
    name: str | None = None
    email: str
    question_count: int


__all__ = ["TrafficQuestionUserUsageResponse"]
