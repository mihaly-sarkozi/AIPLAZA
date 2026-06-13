from __future__ import annotations

PERSON_ENTITY_MIN_CONFIDENCE = 0.5
GIVEN_NAME_CANDIDATE_CONFIDENCE = 0.35


class PersonConfidenceScorer:
    def score(self, *, directory_hit: bool, ambiguous: bool) -> float:
        if not directory_hit:
            return 0.0
        return 0.5 if ambiguous else 0.9

    def score_given_name_candidate(self) -> float:
        return GIVEN_NAME_CANDIDATE_CONFIDENCE


__all__ = [
    "GIVEN_NAME_CANDIDATE_CONFIDENCE",
    "PERSON_ENTITY_MIN_CONFIDENCE",
    "PersonConfidenceScorer",
]
