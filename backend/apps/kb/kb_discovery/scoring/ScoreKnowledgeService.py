from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeScoreDto
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.mapper.discovery_mapper import score_dto_to_orm
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository


class ScoreKnowledgeService:
    _WEIGHTS = {
        "keyword_quality": 0.20,
        "entity_density": 0.20,
        "structure_score": 0.15,
        "source_score": 0.15,
        "length_score": 0.15,
        "language_confidence": 0.15,
    }

    def __init__(self, score_repository: ScoreRepository) -> None:
        self._score_repository = score_repository

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
        *,
        entities: list[KnowledgeEntityDto],
        enrichments: list[KnowledgeEnrichmentDto],
    ) -> list[KnowledgeScoreDto]:
        enrichment_by_chunk = {item.chunk_id: item for item in enrichments}
        entity_counts = self._entity_counts(entities)
        scores: list[KnowledgeScoreDto] = []

        for chunk in chunks:
            enrichment = enrichment_by_chunk.get(chunk.chunk_id)
            keyword_count = int(enrichment.metadata.get("keyword_count", 0)) if enrichment else 0
            components = {
                "keyword_quality": min(1.0, keyword_count / 10.0),
                "entity_density": min(1.0, entity_counts.get(chunk.chunk_id, 0) / 5.0),
                "structure_score": self._structure_score(chunk, enrichment),
                "source_score": 0.8 if ctx.source_type in {"pdf", "docx", "url"} else 0.6,
                "length_score": min(1.0, len(chunk.text) / 500.0),
                "language_confidence": ctx.language_confidence,
            }
            total = round(
                min(1.0, sum(self._WEIGHTS[name] * components[name] for name in self._WEIGHTS)),
                4,
            )
            scores.append(
                KnowledgeScoreDto(
                    chunk_id=chunk.chunk_id,
                    knowledge_score=total,
                    components={key: round(value, 4) for key, value in components.items()},
                )
            )

        self._score_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            [score_dto_to_orm(ctx, score) for score in scores],
        )
        return scores

    @staticmethod
    def _entity_counts(entities: list[KnowledgeEntityDto]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entity in entities:
            for chunk_id in entity.chunk_ids:
                counts[chunk_id] = counts.get(chunk_id, 0) + 1
        return counts

    @staticmethod
    def _structure_score(chunk: DiscoveryChunkDto, enrichment: KnowledgeEnrichmentDto | None) -> float:
        value = 0.4
        if chunk.section_title:
            value += 0.2
        if chunk.chunk_type in {"table", "list", "step", "faq"}:
            value += 0.2
        if enrichment and enrichment.content_type not in {None, "note"}:
            value += 0.2
        return min(1.0, value)


__all__ = ["ScoreKnowledgeService"]
