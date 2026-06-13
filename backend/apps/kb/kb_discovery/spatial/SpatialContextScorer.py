from __future__ import annotations


class SpatialContextScorer:
    def score(self, mention: dict) -> float:
        return 0.9 if mention.get("location_type") == "office" else 0.75


__all__ = ["SpatialContextScorer"]
