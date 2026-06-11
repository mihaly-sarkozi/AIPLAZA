from __future__ import annotations

# backend/apps/kb/kb_understanding/mapper/enrichment_mapper.py
# Feladat: Enrichment / score DTO → ORM átalakítás.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.KnowledgeScoreDto import KnowledgeScoreDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_understanding.orm.KnowledgeScore import KnowledgeScore
from apps.kb.shared.ids import new_id


def enrichment_dto_to_orm(ctx: UnderstandingJobContext, dto: KnowledgeEnrichmentDto) -> KnowledgeEnrichment:
    return KnowledgeEnrichment(
        id=new_id("enrich"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        knowledge_base_id=ctx.knowledge_base_id,
        summary=dto.summary,
        keywords=list(dto.keywords),
        topics=list(dto.topics),
        possible_questions=list(dto.possible_questions),
        content_type=dto.content_type,
        language=dto.language,
        difficulty=dto.difficulty,
        importance=dto.importance,
        confidence=dto.confidence,
    )


def score_dto_to_orm(ctx: UnderstandingJobContext, dto: KnowledgeScoreDto) -> KnowledgeScore:
    return KnowledgeScore(
        id=new_id("score"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        knowledge_base_id=ctx.knowledge_base_id,
        knowledge_score=dto.knowledge_score,
        components=dict(dto.components),
    )


__all__ = ["enrichment_dto_to_orm", "score_dto_to_orm"]
