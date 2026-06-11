from __future__ import annotations

# backend/apps/kb/kb_crud/dto/CreateKnowledgeBaseRequest.py
# Feladat: Tudástár létrehozás HTTP kérés modell.
# Sárközi Mihály - 2026.06.07

from pydantic import BaseModel, Field

from apps.kb.kb_crud.dto.KbPermissionEntry import KbPermissionEntry


class CreateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = Field(default=None, max_length=1024)
    permissions: list[KbPermissionEntry] | None = None


__all__ = ["CreateKnowledgeBaseRequest"]
