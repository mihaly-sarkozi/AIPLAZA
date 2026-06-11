from __future__ import annotations

# backend/apps/kb/kb_crud/dto/SetPermissionsRequest.py
# Feladat: Tudástár jogosultságok beállítása HTTP kérés modell.
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel

from apps.kb.kb_crud.dto.KbPermissionEntry import KbPermissionEntry


class SetPermissionsRequest(BaseModel):
    permissions: list[KbPermissionEntry]


__all__ = ["SetPermissionsRequest"]
