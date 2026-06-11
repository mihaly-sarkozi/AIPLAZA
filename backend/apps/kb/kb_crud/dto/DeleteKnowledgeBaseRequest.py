from __future__ import annotations

# backend/apps/kb/kb_crud/dto/DeleteKnowledgeBaseRequest.py
# Feladat: Tudástár törlés HTTP kérés modell (név megerősítéssel).
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel


class DeleteKnowledgeBaseRequest(BaseModel):
    confirm_name: str


__all__ = ["DeleteKnowledgeBaseRequest"]
