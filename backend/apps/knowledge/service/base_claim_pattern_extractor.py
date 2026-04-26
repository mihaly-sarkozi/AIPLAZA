"""Nyelvi claim-minta extractok közös interfésze."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence

from apps.knowledge.service.claim_candidate import ClaimCandidate


class BaseClaimPatternExtractor(ABC):
    language: ClassVar[str]

    @abstractmethod
    def extract_claim_candidates(self, sentence: Sentence, mentions: list[Mention]) -> list[ClaimCandidate]:
        """Pattern szerinti jelöltek (quality gate a ``ClaimExtractorV1``-ben)."""

    def extract_candidates(self, sentence: Sentence, mentions: list[Mention]) -> list[Claim]:
        """Visszafelé kompatibilitás: jelöltek mint domain ``Claim``."""
        return [c.claim() for c in self.extract_claim_candidates(sentence, mentions)]


__all__ = ["BaseClaimPatternExtractor"]

