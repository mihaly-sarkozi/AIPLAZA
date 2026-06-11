from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/content_mapper.py
# Feladat: Extract / normalize DTO → ORM átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.dto.NormalizedContentDto import NormalizedContentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent
from apps.kb.shared.ids import new_id


def extracted_dto_to_orm(ctx: UnderstandingJobContext, dto: ExtractedContentDto) -> ExtractedContent:
    return ExtractedContent(
        id=new_id("und_extract"),
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        text=dto.text,
        page_map=list(dto.page_map),
        char_count=dto.char_count,
        source_mime=dto.source_mime,
        extractor=dto.extractor,
    )


def normalized_dto_to_orm(ctx: UnderstandingJobContext, dto: NormalizedContentDto) -> NormalizedContent:
    return NormalizedContent(
        id=new_id("und_norm"),
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        text=dto.text,
        page_map=list(dto.page_map),
        char_count=dto.char_count,
        applied_rules=dict(dto.applied_rules),
    )


__all__ = ["extracted_dto_to_orm", "normalized_dto_to_orm"]
