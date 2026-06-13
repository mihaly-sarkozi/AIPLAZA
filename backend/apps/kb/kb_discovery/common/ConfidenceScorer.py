from __future__ import annotations


class ConfidenceScorer:
    def score(self, *, base: float, hits: int = 1, ambiguous: bool = False) -> float:
        value = min(1.0, max(0.0, base))
        if hits > 1:
            value = min(1.0, value + 0.05 * (hits - 1))
        if ambiguous:
            value *= 0.5
        return round(value, 4)


__all__ = ["ConfidenceScorer"]
