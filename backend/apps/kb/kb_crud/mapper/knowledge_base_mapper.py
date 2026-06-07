from __future__ import annotations

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.domain.KnowledgeBaseStatus import KnowledgeBaseStatus
from apps.knowledge.models import KBORM


def _archived_display_name(row: KBORM) -> str:
    if row.deleted_display_name:
        return row.deleted_display_name
    return f"deleted-{row.uuid[:8]}"


def kb_orm_to_domain(row: KBORM) -> KnowledgeBase:
    if row.deleted_at is not None:
        return KnowledgeBase(
            id=row.uuid,
            name=_archived_display_name(row),
            description=row.description,
            status=KnowledgeBaseStatus.ARCHIVED.value,
        )
    return KnowledgeBase(
        id=row.uuid,
        name=row.name,
        description=row.description,
        status=KnowledgeBaseStatus.ACTIVE.value,
    )


__all__ = ["kb_orm_to_domain"]
