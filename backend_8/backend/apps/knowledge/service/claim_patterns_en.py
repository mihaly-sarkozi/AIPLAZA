"""Angol claim-minták és ``EnglishClaimPatternExtractor``.

A lexikai predikátumlista a ``language_rules.LANGUAGE_RULES[\"en\"].predicate_keywords``
mezőben van; ez a modul dokumentálja és egy helyre gyűjti a v1 úton kezelt fő mintákat:

- **uses** / use — pl. modul → technológia
- **must** / should / requires — szabály–eljárás claimek
- **is currently active** — összetett állapot (aux + filler + complement)
- **was inactive** (+ időhatár, pl. „before …”)
- **was created** … **and updated** … — két esemény egy alanyra
- **is the compliance lead at** — címviszony (szervezeti szerep)
- **was previously responsible for** — megjelenítve gyakran ``responsible`` (ld. ``normalize_predicate_display``)
- **was deprecated** / **deprecated** — esemény

A konkrét tokenizálás és subject/object szerkesztés a meglévő ``claim_extract_*`` modulokban történik.
"""
from __future__ import annotations

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.base_claim_pattern_extractor import BaseClaimPatternExtractor
from apps.knowledge.service.claim_candidate import ClaimCandidate
from apps.knowledge.service.claim_extract_v1_core import extract_claims_v1


def en_extract_claims_v1(sentence: Sentence, mentions: list[Mention]) -> list[Claim]:
    """EN minták → claimek (közös mag; EN-specifikus lépések refaktor során ide tehetők)."""
    return extract_claims_v1(sentence, mentions, language="en")


class EnglishClaimPatternExtractor(BaseClaimPatternExtractor):
    language = "en"

    def extract_claim_candidates(self, sentence: Sentence, mentions: list[Mention]) -> list[ClaimCandidate]:
        claims = en_extract_claims_v1(sentence, mentions)
        return [ClaimCandidate.from_claim(c) for c in claims]


__all__ = ["EnglishClaimPatternExtractor", "en_extract_claims_v1"]
