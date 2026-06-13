from __future__ import annotations


class ProcessConfidenceScorer:
    def score(self, item_count: int) -> float:
        return min(1.0, 0.4 + 0.1 * item_count)


__all__ = ["ProcessConfidenceScorer"]
