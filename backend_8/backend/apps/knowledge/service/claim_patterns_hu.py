"""Magyar claim-extrakciós minták: regexek és predikátum-fold halmazok.

A predicate kulcsszavak és egyéb lexikai szabályok továbbra is
``language_rules.LANGUAGE_RULES[\"hu\"]`` alatt vannak; ez a modul csak a
claim pipeline HU-specifikus **mintáit** gyűjti egy helyre.
"""
from __future__ import annotations

import re

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.base_claim_pattern_extractor import BaseClaimPatternExtractor
from apps.knowledge.service.claim_candidate import ClaimCandidate

USE_HEAD_PHRASE_RE = re.compile(
    r"\b((?:a|az)\s+)?((?:[^\s,:;()]+\s+)*)\b(modul|rendszer|szoftver|feature|product|system)\b",
    flags=re.IGNORECASE,
)

HU_USE_PREDICATE_FOLDS: frozenset[str] = frozenset({"hasznal", "hasznalja", "hasznalnia"})

TITLE_RELATION_PREDICATES: frozenset[str] = frozenset({"vezetője", "felelőse"})

WEAK_DUPLICATE_USE_PREDICATE_FOLDS: frozenset[str] = frozenset({"hasznal"})


def hu_extract_claims_v1(sentence: Sentence, mentions: list[Mention]) -> list[Claim]:
    """HU minták → claimek (közös mag hívása; refaktor során ide kerül a HU-specifikus pipeline)."""
    from apps.knowledge.service.claim_extract_v1_core import extract_claims_v1

    return extract_claims_v1(sentence, mentions, language="hu")


class HungarianClaimPatternExtractor(BaseClaimPatternExtractor):
    language = "hu"

    def extract_claim_candidates(self, sentence: Sentence, mentions: list[Mention]) -> list[ClaimCandidate]:
        claims = hu_extract_claims_v1(sentence, mentions)
        return [ClaimCandidate.from_claim(c) for c in claims]


__all__ = [
    "HU_USE_PREDICATE_FOLDS",
    "HungarianClaimPatternExtractor",
    "TITLE_RELATION_PREDICATES",
    "USE_HEAD_PHRASE_RE",
    "WEAK_DUPLICATE_USE_PREDICATE_FOLDS",
    "hu_extract_claims_v1",
]
