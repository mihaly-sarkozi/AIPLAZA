from __future__ import annotations

# backend/apps/kb/kb_crud/mapper/knowledge_base_mapper.py
# Feladat: ORM sor -> domain KnowledgeBase leképezés.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.domain.PersonalDataMode import PersonalDataMode
from apps.kb.kb_crud.domain.PersonalDataSensitivity import PersonalDataSensitivity
from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM


def _display_name(row: KnowledgeBaseORM) -> str:
    if row.deleted_at is not None:
        return row.deleted_display_name or f"deleted-{row.uuid[:8]}"
    return row.name


def kb_orm_to_domain(row: KnowledgeBaseORM) -> KnowledgeBase:
    return KnowledgeBase(
        id=row.id,
        uuid=row.uuid,
        name=_display_name(row),
        description=row.description,
        qdrant_collection_name=row.qdrant_collection_name,
        personal_data_mode=row.personal_data_mode or PersonalDataMode.NO_PERSONAL_DATA.value,
        personal_data_sensitivity=row.personal_data_sensitivity or PersonalDataSensitivity.MEDIUM.value,
        pii_depersonalization_enabled=bool(
            row.pii_depersonalization_enabled if row.pii_depersonalization_enabled is not None else True
        ),
        public_enabled=bool(row.public_enabled or False),
        created_at=row.created_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        deleted_display_name=row.deleted_display_name,
        deleted_training_char_count=max(0, int(row.deleted_training_char_count or 0)),
    )


__all__ = ["kb_orm_to_domain"]
