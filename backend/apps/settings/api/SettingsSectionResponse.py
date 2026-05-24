from __future__ import annotations

# backend/apps/settings/api/SettingsSectionResponse.py
# Feladat: A settings sections response Pydantic sémája a /api/settings/sections route számára.
# Sárközi Mihály - 2026.05.24

from pydantic import BaseModel


class SettingsSectionResponse(BaseModel):
    key: str
    label: str
    path: str
    permission: str
    order: int
    description: str = ""
    source: str = "core"


__all__ = ["SettingsSectionResponse"]
