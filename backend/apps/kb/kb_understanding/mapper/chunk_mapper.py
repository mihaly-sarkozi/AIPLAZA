from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/chunk_mapper.py
# Feladat: KnowledgeChunkDto → ORM átalakítás a kötelező bizonyíték-metaadatokkal.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk


def chunk_dto_to_orm(
    ctx: UnderstandingJobContext,
    dto: KnowledgeChunkDto,
    *,
    version: int = 1,
) -> KnowledgeChunk:
    return KnowledgeChunk(
        id=dto.chunk_id,
        job_id=ctx.job_id,
        document_id=ctx.training_item_id,
        source_id=ctx.raw_ref,
        knowledge_base_id=ctx.knowledge_base_id,
        file_name=ctx.file_name,
        source_type=ctx.source_type,
        checksum=dto.checksum,
        version=version,
        page_number=dto.page_number,
        section_title=dto.section_title,
        order_index=dto.order_index,
        chunk_type=dto.chunk_type.value,
        text=dto.text,
        token_count=dto.token_count,
        created_by=ctx.created_by,
        metadata_json={
            "title": ctx.title,
            "content_hash": ctx.content_hash,
            **dict(dto.metadata or {}),
        },
    )


__all__ = ["chunk_dto_to_orm"]
