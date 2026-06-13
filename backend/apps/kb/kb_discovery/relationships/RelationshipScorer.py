from __future__ import annotations


class RelationshipScorer:
    def score(self, rel: dict) -> float:
        return float(rel.get("confidence") or 0.5)


__all__ = ["RelationshipScorer"]
