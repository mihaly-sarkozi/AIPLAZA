# backend/apps/traffic/schemas/TrafficQuestionReservationResult.py
# Feladat: A kérdésfoglalás eredmény DTO-ja. Megmondja, hogy a DB-atomikus quota reserve sikerült-e, és mennyi keret maradt.

from __future__ import annotations

from pydantic import BaseModel


class TrafficQuestionReservationResult(BaseModel):
    """A traffic kérdésfoglalás eredménye chat és quota ellenőrzéshez."""

    allowed: bool
    reason: str | None = None
    period_key: str
    used_total: int
    available_total: int
    remaining_total: int


__all__ = ["TrafficQuestionReservationResult"]
