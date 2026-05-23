"""Spanyol claim-minták és ``SpanishClaimPatternExtractor``.

A predikátum-tokenek ``language_rules.LANGUAGE_RULES[\"es\"].predicate_keywords`` alatt
vannak; a modul a v1 út fő ES mintáit dokumentálja:

- **utiliza** / usa — modul/szolgáltatás → technológia
- **debe** / debería — szabály–eljárás
- **está actualmente activa** — összetett állapot (aux + filler + complement, ``merge_compound_predicates``)
- **estaba inactiva** (+ időhatár, pl. „en 2024”)
- **fue creada** … **y actualizada** … — két esemény egy alanyra
- **es el responsable de** / **es** + tárgy — szerepkör (pl. compliance)
- **fue responsable anteriormente de** — történeti felelősség (hosszú frázis a predikátumlistában)
- **fue desactivado** / desactivado — esemény

A subject/object szerkesztés a meglévő ``claim_extract_*`` modulokban történik.
"""
from __future__ import annotations

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.service.base_claim_pattern_extractor import BaseClaimPatternExtractor
from apps.knowledge.service.claim_candidate import ClaimCandidate
from apps.knowledge.service.claim_extract_v1_core import extract_claims_v1


def es_extract_claims_v1(sentence: Sentence, mentions: list[Mention]) -> list[Claim]:
    """ES minták → claimek (közös mag; ES-specifikus lépések refaktor során ide tehetők)."""
    return extract_claims_v1(sentence, mentions, language="es")


class SpanishClaimPatternExtractor(BaseClaimPatternExtractor):
    language = "es"

    def extract_claim_candidates(self, sentence: Sentence, mentions: list[Mention]) -> list[ClaimCandidate]:
        claims = es_extract_claims_v1(sentence, mentions)
        return [ClaimCandidate.from_claim(c) for c in claims]


__all__ = ["SpanishClaimPatternExtractor", "es_extract_claims_v1"]
