from __future__ import annotations

from typing import Any


class HybridRankService:
    def __init__(
        self,
        *,
        vector_score_weight: float = 0.75,
        knowledge_score_weight: float = 0.25,
        freshness_weight: float = 0.0,
        source_quality_weight: float = 0.0,
    ) -> None:
        self._vector_w = vector_score_weight
        self._knowledge_w = knowledge_score_weight
        self._freshness_w = freshness_weight
        self._source_w = source_quality_weight

    def rank(self, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        for hit in hits:
            payload = dict(hit.get("payload") or {})
            qdrant_score = float(hit.get("score") or 0.0)
            overall = float(payload.get("overall_score") or 0.5)
            freshness = float(payload.get("freshness_score") or 0.0)
            source_score = float(payload.get("source_score") or 0.0)
            hybrid = (
                self._vector_w * qdrant_score
                + self._knowledge_w * overall
                + self._freshness_w * freshness
                + self._source_w * source_score
            )
            row = dict(hit)
            row["hybrid_score"] = hybrid
            row["overall_score"] = overall
            ranked.append(row)
        ranked.sort(key=lambda item: float(item.get("hybrid_score") or 0.0), reverse=True)
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
        return ranked


__all__ = ["HybridRankService"]
