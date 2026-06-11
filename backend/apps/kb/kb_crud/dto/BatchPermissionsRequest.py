from __future__ import annotations

# backend/apps/kb/kb_crud/dto/BatchPermissionsRequest.py
# Feladat: Több tudástár jogosultságainak lekérése HTTP kérés modell.
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel, Field


class BatchPermissionsRequest(BaseModel):
    uuids: list[str] = Field(default_factory=list, max_length=100)


__all__ = ["BatchPermissionsRequest"]
