from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
    KnowledgeKeywordDto,
    KnowledgeScoreDto,
    KnowledgeScoringInput,
    KnowledgeTopicDto,
    ProcessMentionDto,
    SpatialMentionDto,
    TemporalMentionDto,
)
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.mapper.discovery_mapper import score_dto_to_orm
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.scoring.EntityDensityScore import EntityDensityScore
from apps.kb.kb_discovery.scoring.FinalKnowledgeScore import FinalKnowledgeScore
from apps.kb.kb_discovery.scoring.FreshnessScore import FreshnessScore
from apps.kb.kb_discovery.scoring.KeywordQualityScore import KeywordQualityScore
from apps.kb.kb_discovery.scoring.SpatialScore import SpatialScore
from apps.kb.kb_discovery.scoring.StructureScore import StructureScore
from apps.kb.kb_discovery.scoring.TemporalScore import TemporalScore


class KnowledgeScoringService:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self._score_repository = score_repository
        self._freshness = FreshnessScore()
        self._structure = StructureScore()
        self._entity_density = EntityDensityScore()
        self._keyword_quality = KeywordQualityScore()
        self._temporal = TemporalScore()
        self._spatial = SpatialScore()
        self._final = FinalKnowledgeScore()

    def run(self, ctx: DiscoveryJobContext, scoring_input: KnowledgeScoringInput) -> list[KnowledgeScoreDto]:
        chunks = list(scoring_input.chunks)
        enrichments_by_chunk = {item.chunk_id: item for item in scoring_input.enrichments}
        entity_counts = self._entity_density.counts(list(scoring_input.entities))
        keyword_counts = self._keyword_quality.counts(list(scoring_input.keywords))
        temporal_counts = self._temporal.counts(list(scoring_input.temporal_mentions))
        spatial_counts = self._spatial.counts(list(scoring_input.spatial_mentions))
        process_counts = self._process_counts(list(scoring_input.process_mentions))
        topic_counts: dict[str, int] = {}
        for topic in scoring_input.topics:
            topic_counts[topic.chunk_id] = topic_counts.get(topic.chunk_id, 0) + 1

        relationship_score = min(1.0, scoring_input.relationship_count / max(len(chunks), 1) / 5.0)
        source_score = 0.8 if ctx.source_type in {"pdf", "docx", "url"} else 0.6

        scores: list[KnowledgeScoreDto] = []
        for chunk in chunks:
            enrichment = enrichments_by_chunk.get(chunk.chunk_id)
            language_confidence = (
                enrichment.language_confidence
                if enrichment is not None
                else chunk.language_confidence or ctx.language_confidence
            )
            content_type = enrichment.content_type if enrichment is not None else "general_text"
            components = {
                "language_confidence": round(language_confidence, 4),
                "freshness_score": self._freshness.score(),
                "structure_score": self._structure.score(chunk),
                "entity_density_score": self._entity_density.score(entity_counts.get(chunk.chunk_id, 0)),
                "keyword_quality_score": self._keyword_quality.score(keyword_counts.get(chunk.chunk_id, 0)),
                "topic_coverage_score": min(1.0, 0.3 * topic_counts.get(chunk.chunk_id, 0)),
                "temporal_score": self._temporal.score(temporal_counts.get(chunk.chunk_id, 0)),
                "spatial_score": self._spatial.score(spatial_counts.get(chunk.chunk_id, 0)),
                "process_score": self._process_score(process_counts.get(chunk.chunk_id, 0)),
                "relationship_score": round(relationship_score, 4),
                "content_type_score": 0.8 if content_type not in {"unknown", "general_text"} else 0.4,
                "source_quality_score": source_score,
            }
            total = self._final.score(components)
            scores.append(
                KnowledgeScoreDto(
                    chunk_id=chunk.chunk_id,
                    knowledge_score=total,
                    components=components,
                )
            )
        self._score_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            [score_dto_to_orm(ctx, score) for score in scores],
        )
        return scores

    @staticmethod
    def _process_counts(process_mentions: list[ProcessMentionDto]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for mention in process_mentions:
            counts[mention.chunk_id] = counts.get(mention.chunk_id, 0) + 1
        return counts

    @staticmethod
    def _process_score(process_count: int) -> float:
        return min(1.0, process_count / 3.0)


__all__ = ["KnowledgeScoringService"]
