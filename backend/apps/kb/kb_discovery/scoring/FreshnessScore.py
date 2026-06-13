from __future__ import annotations


class FreshnessScore:
    def score(self) -> float:
        return 1.0


class StructureScore:
    def score(self, chunk) -> float:
        value = 0.4
        if chunk.section_title:
            value += 0.3
        if chunk.chunk_type in {"table", "list", "step", "faq"}:
            value += 0.3
        return min(1.0, value)


class EntityDensityScore:
    def counts(self, entities) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entity in entities:
            for chunk_id in entity.chunk_ids:
                counts[chunk_id] = counts.get(chunk_id, 0) + 1
        return counts

    def score(self, entity_count: int) -> float:
        return min(1.0, entity_count / 5.0)


class KeywordQualityScore:
    def counts(self, keywords) -> dict[str, int]:
        counts: dict[str, int] = {}
        for keyword in keywords:
            counts[keyword.chunk_id] = counts.get(keyword.chunk_id, 0) + 1
        return counts

    def score(self, keyword_count: int) -> float:
        return min(1.0, keyword_count / 10.0)


class TemporalScore:
    def counts(self, temporal) -> dict[str, int]:
        counts: dict[str, int] = {}
        for mention in temporal:
            counts[mention.chunk_id] = counts.get(mention.chunk_id, 0) + 1
        return counts

    def score(self, temporal_count: int) -> float:
        return 1.0 if temporal_count else 0.0


class SpatialScore:
    def counts(self, spatial) -> dict[str, int]:
        counts: dict[str, int] = {}
        for mention in spatial:
            counts[mention.chunk_id] = counts.get(mention.chunk_id, 0) + 1
        return counts

    def score(self, spatial_count: int) -> float:
        return 1.0 if spatial_count else 0.0


class FinalKnowledgeScore:
    _WEIGHTS = {
        "language_confidence": 0.08,
        "freshness_score": 0.06,
        "structure_score": 0.10,
        "entity_density_score": 0.10,
        "keyword_quality_score": 0.12,
        "topic_coverage_score": 0.10,
        "temporal_score": 0.08,
        "spatial_score": 0.08,
        "process_score": 0.08,
        "relationship_score": 0.10,
        "content_type_score": 0.10,
        "source_quality_score": 0.10,
    }

    def score(self, components: dict[str, float]) -> float:
        total = sum(self._WEIGHTS[name] * components.get(name, 0.0) for name in self._WEIGHTS)
        return round(min(1.0, max(0.0, total)), 4)


__all__ = [
    "EntityDensityScore",
    "FinalKnowledgeScore",
    "FreshnessScore",
    "KeywordQualityScore",
    "SpatialScore",
    "StructureScore",
    "TemporalScore",
]
