from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/structure_mapper.py
# Feladat: StructuredBlockDto → ORM átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.StructuredBlockDto import StructuredBlockDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.StructuredBlock import StructuredBlock
from apps.kb.shared.ids import new_id


def block_dto_to_orm(ctx: UnderstandingJobContext, dto: StructuredBlockDto) -> StructuredBlock:
    return StructuredBlock(
        id=new_id("und_block"),
        job_id=ctx.job_id,
        training_item_id=ctx.training_item_id,
        knowledge_base_id=ctx.knowledge_base_id,
        block_type=dto.block_type.value,
        text=dto.text,
        order_index=dto.order_index,
        page_number=dto.page_number,
        section_title=dto.section_title,
        metadata_json=dict(dto.metadata or {}),
    )


__all__ = ["block_dto_to_orm"]
