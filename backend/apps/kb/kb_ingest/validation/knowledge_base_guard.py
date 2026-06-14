from __future__ import annotations

from sqlalchemy import select

from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.validation.TrainingValidationError import TrainingValidationError


def require_active_knowledge_base(session_factory, knowledge_base_id: str) -> None:
    kb_id = str(knowledge_base_id or "").strip()
    if not kb_id:
        raise TrainingValidationError(
            TrainingErrorCode.VALIDATION_ERROR,
            reason="Knowledge base id is required.",
        )
    with session_factory() as session:
        exists = session.execute(
            select(KnowledgeBaseORM.id).where(
                KnowledgeBaseORM.uuid == kb_id,
                KnowledgeBaseORM.deleted_at.is_(None),
            ).limit(1)
        ).scalar_one_or_none()
    if exists is None:
        raise TrainingValidationError(
            TrainingErrorCode.KNOWLEDGE_BASE_NOT_FOUND,
            reason=f"Knowledge base not found: {kb_id}",
        )


__all__ = ["require_active_knowledge_base"]
