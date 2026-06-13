from __future__ import annotations

PERSON_ENTITY_MIN_CONFIDENCE = 0.5
GIVEN_NAME_CANDIDATE_CONFIDENCE = 0.35
FULL_NAME_BASE_CONFIDENCE = 0.70
FULL_NAME_DIRECTORY_CONFIDENCE = 0.75


class PersonConfidenceScorer:
    def score(self, *, directory_hit: bool, ambiguous: bool) -> float:
        if not directory_hit:
            return 0.0
        return 0.5 if ambiguous else 0.9

    def score_given_name_candidate(self) -> float:
        return GIVEN_NAME_CANDIDATE_CONFIDENCE

    def score_full_name(
        self,
        *,
        directory_hit: bool,
        email_nearby: bool = False,
        signature_nearby: bool = False,
    ) -> float:
        confidence = FULL_NAME_DIRECTORY_CONFIDENCE if directory_hit else FULL_NAME_BASE_CONFIDENCE
        if email_nearby:
            confidence += 0.05
        if signature_nearby:
            confidence += 0.05
        return min(confidence, 0.85)


__all__ = [
    "FULL_NAME_BASE_CONFIDENCE",
    "FULL_NAME_DIRECTORY_CONFIDENCE",
    "GIVEN_NAME_CANDIDATE_CONFIDENCE",
    "PERSON_ENTITY_MIN_CONFIDENCE",
    "PersonConfidenceScorer",
]
