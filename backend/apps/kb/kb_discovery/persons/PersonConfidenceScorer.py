from __future__ import annotations


class PersonConfidenceScorer:
    def score(self, *, directory_hit: bool, ambiguous: bool) -> float:
        if not directory_hit:
            return 0.0
        return 0.5 if ambiguous else 0.9


__all__ = ["PersonConfidenceScorer"]
