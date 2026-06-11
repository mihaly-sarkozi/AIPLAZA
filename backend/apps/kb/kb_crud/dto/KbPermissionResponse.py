from __future__ import annotations

# backend/apps/kb/kb_crud/dto/KbPermissionResponse.py
# Feladat: Egy felhasználó tudástár jogosultsága a válaszban (a korábbi KBPermissionOut paritásával).
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel


class KbPermissionResponse(BaseModel):
    user_id: int
    email: str
    name: str | None = None
    permission: str
    role: str


__all__ = ["KbPermissionResponse"]
