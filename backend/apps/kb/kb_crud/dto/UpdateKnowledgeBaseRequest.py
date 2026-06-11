from __future__ import annotations

# backend/apps/kb/kb_crud/dto/UpdateKnowledgeBaseRequest.py
# Feladat: Tudástár módosítás HTTP kérés modell.
# Sárközi Mihály - 2026.06.07

from pydantic import BaseModel, Field

from apps.kb.kb_crud.domain.PersonalDataMode import PersonalDataMode


class UpdateKnowledgeBaseRequest(BaseModel):
    name: str = Field(..., max_length=200)
    description: str | None = Field(default=None, max_length=1024)
    personal_data_mode: PersonalDataMode | None = None
    pii_depersonalization_enabled: bool | None = None
    public_enabled: bool | None = None


__all__ = ["UpdateKnowledgeBaseRequest"]
