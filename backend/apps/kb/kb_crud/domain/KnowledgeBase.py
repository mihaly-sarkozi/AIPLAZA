from __future__ import annotations

# backend/apps/kb/kb_crud/domain/KnowledgeBase.py
# Feladat: Tudástár domain entitás (ORM-független, immutábilis).
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass
from datetime import datetime

from apps.kb.kb_crud.domain.KnowledgeBaseStatus import KnowledgeBaseStatus


@dataclass(frozen=True)
class KnowledgeBase:
    """Tudástár törzsadat a service réteg számára.

    Az ``id`` a belső (tenant sémán belüli) numerikus azonosító, a ``uuid`` a
    kifelé publikált stabil azonosító.
    """

    id: int | None
    uuid: str
    name: str
    description: str | None
    qdrant_collection_name: str
    personal_data_mode: str
    personal_data_sensitivity: str
    pii_depersonalization_enabled: bool
    public_enabled: bool
    created_at: datetime | None
    updated_at: datetime | None
    deleted_at: datetime | None = None
    deleted_display_name: str | None = None
    deleted_training_char_count: int = 0

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def status(self) -> KnowledgeBaseStatus:
        return KnowledgeBaseStatus.DELETED if self.is_deleted else KnowledgeBaseStatus.ACTIVE


__all__ = ["KnowledgeBase"]
