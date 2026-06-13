from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.shared.ids import new_id
from shared.utils.clock import utc_now_naive


def enrichment_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeEnrichmentDto) -> KnowledgeEnrichment:
    now = utc_now_naive()
    return KnowledgeEnrichment(
        id=new_id("enrich"),
        job_id=ctx.job_id,
        knowledge_base_id=ctx.knowledge_base_id,
        training_item_id=ctx.training_item_id,
        chunk_id=dto.chunk_id,
        language_code=dto.language_code,
        language_confidence=dto.language_confidence,
        lead_sentence=dto.lead_sentence,
        preview_text=dto.preview_text,
        content_type=dto.content_type,
        content_type_confidence=dto.content_type_confidence,
        profile_confidence=dto.profile_confidence,
        metadata_json=dict(dto.metadata),
        created_at=now,
        updated_at=now,
    )


__all__ = ["enrichment_dto_to_orm"]
