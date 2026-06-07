# backend/apps/traffic/schemas/TrafficOverviewResponse.py
# Feladat: A /traffic/overview endpoint teljes read modell response DTO-ja.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from apps.traffic.schemas.TrafficCatalogEntryResponse import TrafficCatalogEntryResponse


class TrafficOverviewResponse(BaseModel):
    """A /traffic/overview endpoint teljes read modellje a frontend forgalom oldalhoz."""

    current_period_key: str
    current_period_start_iso: str
    current_period_end_iso: str
    catalog: list[TrafficCatalogEntryResponse]
    subscription: dict[str, Any]
    limits: dict[str, Any]
    usage: dict[str, Any]


__all__ = ["TrafficOverviewResponse"]
