from __future__ import annotations

# backend/apps/kb/kb_crud/service/KnowledgeBaseResponseMapper.py
# Feladat: Domain KnowledgeBase -> HTTP válasz modell leképezés.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse


def to_response(
    kb: KnowledgeBase,
    *,
    can_train: bool | None = None,
    has_training: bool = False,
    storage_metrics: dict[str, int] | None = None,
) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        uuid=kb.uuid,
        name=kb.name,
        description=kb.description,
        qdrant_collection_name=kb.qdrant_collection_name,
        personal_data_mode=kb.personal_data_mode,
        personal_data_sensitivity=kb.personal_data_sensitivity,
        pii_depersonalization_enabled=kb.pii_depersonalization_enabled,
        public_enabled=kb.public_enabled,
        is_public=kb.public_enabled,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        deleted_at=kb.deleted_at,
        status=kb.status,
        can_train=can_train,
        has_training=has_training,
        storage_metrics=storage_metrics or {},
    )


__all__ = ["to_response"]
