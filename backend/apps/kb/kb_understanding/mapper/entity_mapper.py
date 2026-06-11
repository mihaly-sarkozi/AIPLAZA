from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/entity_mapper.py
# Feladat: KnowledgeEntityDto → ORM átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.shared.ids import new_id


def entity_dto_to_orm(ctx: UnderstandingJobContext, dto: KnowledgeEntityDto) -> KnowledgeEntity:
    return KnowledgeEntity(
        id=new_id("entity"),
        job_id=ctx.job_id,
        document_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        entity_type=dto.entity_type.value,
        name=dto.name[:512],
        normalized_name=dto.normalized_name[:512],
        aliases=list(dto.aliases),
        confidence=dto.confidence,
        chunk_ids=list(dto.chunk_ids),
    )


__all__ = ["entity_dto_to_orm"]
