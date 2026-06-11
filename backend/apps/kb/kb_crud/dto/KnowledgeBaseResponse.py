from __future__ import annotations

# backend/apps/kb/kb_crud/dto/KnowledgeBaseResponse.py
# Feladat: Tudástár HTTP válasz modell (a korábbi KBOut paritásával).
# Sárközi Mihály - 2026.06.07

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_crud.domain.KnowledgeBaseStatus import KnowledgeBaseStatus
from apps.kb.kb_crud.domain.PersonalDataMode import PersonalDataMode
from apps.kb.kb_crud.domain.PersonalDataSensitivity import PersonalDataSensitivity


class KnowledgeBaseResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    uuid: str
    name: str
    description: str | None = None
    qdrant_collection_name: str
    personal_data_mode: str = PersonalDataMode.NO_PERSONAL_DATA.value
    personal_data_sensitivity: str = PersonalDataSensitivity.MEDIUM.value
    pii_depersonalization_enabled: bool = True
    public_enabled: bool = False
    is_public: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted_at: datetime | None = None
    status: KnowledgeBaseStatus = KnowledgeBaseStatus.ACTIVE
    can_train: bool | None = None
    has_training: bool = False
    storage_metrics: dict[str, int] = Field(default_factory=dict)


__all__ = ["KnowledgeBaseResponse"]
