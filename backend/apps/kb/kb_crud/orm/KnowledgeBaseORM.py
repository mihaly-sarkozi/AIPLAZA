from __future__ import annotations

# backend/apps/kb/kb_crud/orm/KnowledgeBaseORM.py
# Feladat: Tudástár (knowledge base) perzisztencia — a `knowledge_bases` tábla ORM definíciója.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String

from apps.kb.kb_crud.domain.PersonalDataMode import PersonalDataMode
from apps.kb.kb_crud.domain.PersonalDataSensitivity import PersonalDataSensitivity
from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeBaseORM(TenantSchemaBase):
    """Egy tenant tudástárának törzsadata.

    Soft delete: törléskor a ``deleted_at`` kitöltődik, a ``name`` technikai névre
    íródik át, az eredeti név a ``deleted_display_name``-ben marad meg, a tanított
    karakterszám pedig a ``deleted_training_char_count``-ban.
    """

    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(200), unique=True, nullable=False)
    description = Column(String(1024))
    qdrant_collection_name = Column(String(128), unique=True, nullable=False)
    personal_data_mode = Column(String(32), nullable=False, default=PersonalDataMode.NO_PERSONAL_DATA.value)
    personal_data_sensitivity = Column(String(16), nullable=False, default=PersonalDataSensitivity.MEDIUM.value)
    pii_depersonalization_enabled = Column(Boolean, nullable=False, default=True)
    public_enabled = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utc_now_naive)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    updated_by = Column(Integer, nullable=False)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_display_name = Column(String(200), nullable=True)
    deleted_training_char_count = Column(BigInteger, nullable=False, default=0)


__all__ = ["KnowledgeBaseORM"]
