"""Claim jelölt a quality gate előtt (pattern extract → domain ``Claim``).

A ``claim_split`` NLP csomag ``ClaimCandidate`` típusától elkülönül: az ottani jelölt
token-spannal írja le a finom szegmentálást; ez a modul a v1 pattern-pipeline
kimenetét fedi (subject/predicate/object már ismert).
"""
from __future__ import annotations

from dataclasses import dataclass

from apps.knowledge.domain.claim import Claim


@dataclass(frozen=True)
class ClaimCandidate:
    """Extrakciós jelölt; belsőleg teljes ``Claim`` (mention id-k, meta, típus)."""

    draft: Claim

    @classmethod
    def from_claim(cls, claim: Claim) -> ClaimCandidate:
        return cls(draft=claim)

    def claim(self) -> Claim:
        """Domain claim a gate és a ``ClaimExtractorV1.build_claim_from_candidate`` számára."""
        return self.draft


__all__ = ["ClaimCandidate"]
