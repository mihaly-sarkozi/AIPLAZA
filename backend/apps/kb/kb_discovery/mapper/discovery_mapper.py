from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
    KnowledgeKeywordDto,
    KnowledgeScoreDto,
    KnowledgeTopicDto,
    SpatialMentionDto,
    TemporalMentionDto,
)
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic
from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention
from apps.kb.kb_discovery.orm.TemporalMention import TemporalMention
from apps.kb.shared.ids import new_id


def entity_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeEntityDto) -> KnowledgeEntity:
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


def mention_dto_from_candidate(
    ctx: DiscoveryJobContext,
    chunk: DiscoveryChunkDto | None,
    candidate: EntityCandidate,
) -> EntityMentionDto:
    page_numbers: tuple[int, ...] = ()
    source_part_ids: tuple[str, ...] = ()
    language_code = candidate.language_code
    if chunk is not None:
        if chunk.page_number is not None:
            page_numbers = (chunk.page_number,)
        raw_part_ids = chunk.metadata.get("source_part_ids") or []
        source_part_ids = tuple(str(item) for item in raw_part_ids if item)
        if language_code is None:
            language_code = chunk.language_code
    metadata = dict(candidate.metadata)
    return EntityMentionDto(
        entity_type=candidate.entity_type,
        chunk_id=candidate.chunk_id,
        raw_text=candidate.name,
        normalized_name=candidate.normalized_name,
        start_offset=candidate.start_offset,
        end_offset=candidate.end_offset,
        confidence=candidate.confidence,
        source=candidate.source,
        language_code=language_code,
        subtype=candidate.subtype,
        recognizer_name=candidate.source,
        metadata=metadata,
        page_numbers=page_numbers,
        source_part_ids=source_part_ids,
    )


def mention_dto_to_orm(ctx: DiscoveryJobContext, dto: EntityMentionDto) -> EntityMention:
    return EntityMention(
        id=new_id("mention"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        knowledge_base_id=ctx.knowledge_base_id,
        training_item_id=ctx.training_item_id,
        entity_type=dto.entity_type.value,
        raw_text=dto.raw_text[:512],
        normalized_name=dto.normalized_name[:512],
        start_offset=dto.start_offset,
        end_offset=dto.end_offset,
        confidence=dto.confidence,
        source=dto.source or None,
        language_code=dto.language_code,
        subtype=dto.subtype,
        recognizer_name=dto.recognizer_name or dto.source or None,
        page_numbers=list(dto.page_numbers),
        source_part_ids=list(dto.source_part_ids),
        metadata_json=dict(dto.metadata),
    )


def keyword_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeKeywordDto) -> KnowledgeKeyword:
    return KnowledgeKeyword(
        id=new_id("keyword"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        term=dto.term[:256],
        rank=dto.rank,
        score=dto.score,
    )


def topic_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeTopicDto) -> KnowledgeTopic:
    return KnowledgeTopic(
        id=new_id("topic"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        topic_key=dto.topic_key[:128],
        confidence=dto.confidence,
    )


def temporal_dto_to_orm(ctx: DiscoveryJobContext, dto: TemporalMentionDto) -> TemporalMention:
    return TemporalMention(
        id=new_id("temporal"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        raw_text=dto.raw_text[:256],
        normalized_start=dto.normalized_start,
        normalized_end=dto.normalized_end,
        temporal_type=dto.temporal_type,
        confidence=dto.confidence,
    )


def spatial_dto_to_orm(ctx: DiscoveryJobContext, dto: SpatialMentionDto) -> SpatialMention:
    return SpatialMention(
        id=new_id("spatial"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        raw_text=dto.raw_text[:512],
        normalized_location=dto.normalized_location[:512],
        location_type=dto.location_type,
        site_id=dto.site_id,
        confidence=dto.confidence,
    )


def score_dto_to_orm(ctx: DiscoveryJobContext, dto: KnowledgeScoreDto) -> KnowledgeScore:
    return KnowledgeScore(
        id=new_id("score"),
        job_id=ctx.job_id,
        chunk_id=dto.chunk_id,
        knowledge_base_id=ctx.knowledge_base_id,
        knowledge_score=dto.knowledge_score,
        components=dict(dto.components),
    )


__all__ = [
    "entity_dto_to_orm",
    "keyword_dto_to_orm",
    "mention_dto_from_candidate",
    "mention_dto_to_orm",
    "score_dto_to_orm",
    "spatial_dto_to_orm",
    "temporal_dto_to_orm",
    "topic_dto_to_orm",
]
