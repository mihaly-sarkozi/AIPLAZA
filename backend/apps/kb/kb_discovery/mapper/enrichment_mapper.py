from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.shared.ids import new_id


def enrichment_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeEnrichmentDto) -> KnowledgeEnrichment:
    return KnowledgeEnrichment(
        id=new_id("enrich"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        lead_sentence=dto.lead_sentence,
        keywords=list(dto.keywords),
        topics=list(dto.topics),
        content_type=dto.content_type,
        language_code=dto.language_code,
        language_confidence=dto.language_confidence,
        possible_questions=list(dto.possible_questions),
        confidence=dto.confidence,
    )


__all__ = ["enrichment_dto_to_orm"]
