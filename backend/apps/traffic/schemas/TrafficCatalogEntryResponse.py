# backend/apps/traffic/schemas/TrafficCatalogEntryResponse.py
# Feladat: Egy forgalom oldalon megjeleníthető csomag vagy addon catalog tétel response DTO-ja.

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TrafficCatalogEntryResponse(BaseModel):
    """Egy traffic oldalon megjeleníthető csomag vagy addon catalog tétel."""

    entry_type: str
    code: str
    name: str
    currency: str
    price_cents: int
    price: float
    included: dict[str, Any]
    metadata: dict[str, Any]


__all__ = ["TrafficCatalogEntryResponse"]
