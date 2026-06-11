from __future__ import annotations

# backend/apps/kb/kb_crud/dto/KbPermissionEntry.py
# Feladat: Egy felhasználó-jogosultság pár a kérésekben (use/train/none).
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel

from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel


class KbPermissionEntry(BaseModel):
    user_id: int
    permission: KbPermissionLevel = KbPermissionLevel.NONE


__all__ = ["KbPermissionEntry"]
