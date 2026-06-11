from __future__ import annotations

# backend/apps/kb/kb_understanding/service/ScoreKnowledgeService.py
# Feladat: Chunk-szintű minőségi / rangsorolási alappontszám számítása komponensekből.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.dto.KnowledgeScoreDto import KnowledgeScoreDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.ChunkType import ChunkType
from apps.kb.kb_understanding.mapper.enrichment_mapper import score_dto_to_orm
from apps.kb.kb_understanding.repository.ScoreRepository import ScoreRepository

# Komponens súlyok — az összeg 1.0.
_WEIGHTS = {
    "freshness": 0.15,
    "structure": 0.20,
    "source_type": 0.10,
    "entity_density": 0.15,
    "length": 0.20,
    "enrichment_confidence": 0.20,
}

_SOURCE_TYPE_SCORES = {"file": 1.0, "url": 0.7, "text": 0.8}
_STRUCTURED_CHUNK_TYPES = {
    ChunkType.TABLE,
    ChunkType.LIST,
    ChunkType.STEP,
    ChunkType.FAQ,
}
_IDEAL_MIN_CHARS = 300
_IDEAL_MAX_CHARS = 1800


class ScoreKnowledgeService:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self._score_repository = score_repository

    def run(
        self,
        ctx: UnderstandingJobContext,
        chunks: list[KnowledgeChunkDto],
        entities: list[KnowledgeEntityDto],
        enrichments: list[KnowledgeEnrichmentDto] | None = None,
    ) -> list[KnowledgeScoreDto]:
        entity_counts: dict[str, int] = {}
        for entity in entities:
            for chunk_id in entity.chunk_ids:
                entity_counts[chunk_id] = entity_counts.get(chunk_id, 0) + 1
        enrichment_by_chunk = {
            enrichment.chunk_id: enrichment for enrichment in enrichments or []
        }

        scores: list[KnowledgeScoreDto] = []
        for chunk in chunks:
            enrichment = enrichment_by_chunk.get(chunk.chunk_id)
            components = {
                # Most feldolgozott tartalom — teljes frissesség; később a maintenance csökkenti.
                "freshness": 1.0,
                "structure": self._structure_score(chunk),
                "source_type": _SOURCE_TYPE_SCORES.get(ctx.source_type, 0.5),
                "entity_density": self._entity_density_score(entity_counts.get(chunk.chunk_id, 0)),
                "length": self._length_score(len(chunk.text)),
                "enrichment_confidence": enrichment.confidence if enrichment else 0.0,
            }
            total = sum(_WEIGHTS[name] * value for name, value in components.items())
            scores.append(
                KnowledgeScoreDto(
                    chunk_id=chunk.chunk_id,
                    knowledge_score=round(min(1.0, max(0.0, total)), 4),
                    components={name: round(value, 4) for name, value in components.items()},
                )
            )

        self._score_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            [score_dto_to_orm(ctx, score) for score in scores],
        )
        return scores

    @staticmethod
    def _structure_score(chunk: KnowledgeChunkDto) -> float:
        score = 0.4
        if chunk.section_title:
            score += 0.3
        if chunk.chunk_type in _STRUCTURED_CHUNK_TYPES:
            score += 0.3
        return min(1.0, score)

    @staticmethod
    def _entity_density_score(entity_count: int) -> float:
        # 0 entitás → 0; 5+ entitás → 1.0.
        return min(1.0, entity_count / 5.0)

    @staticmethod
    def _length_score(char_count: int) -> float:
        if char_count <= 0:
            return 0.0
        if char_count < _IDEAL_MIN_CHARS:
            return char_count / _IDEAL_MIN_CHARS
        if char_count <= _IDEAL_MAX_CHARS:
            return 1.0
        return max(0.3, _IDEAL_MAX_CHARS / char_count)


__all__ = ["ScoreKnowledgeService"]
