from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.GivenNameGazetteer import GivenNameGazetteer
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import PersonConfidenceScorer

_GIVEN_NAME_TOKEN = re.compile(
    r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{1,})\b",
    re.UNICODE,
)


class GivenNameRecognizer(BaseRecognizer):
    """Gyenge jelölés — önmagában nem hoz létre végleges PERSON entity-t.

    Szerepe:
    - FullPersonNameRecognizer gazetteer jel forrása
    - jövőbeli context boost (email/aláírás közeli jel)
    - alacsony confidence candidate (GIVEN_NAME_CANDIDATE_CONFIDENCE)

    A PersonRecognitionService csak >= PERSON_ENTITY_MIN_CONFIDENCE értéket persistál.
    """

    name = "given_name"
    version = "1.0"

    def __init__(self, gazetteer: GivenNameGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or GivenNameGazetteer()
        self._normalizer = TextNormalizer()
        self._scorer = PersonConfidenceScorer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            known = self._gazetteer.names_for(chunk.language_code)
            if not known:
                continue
            by_normalized = {self._normalizer.normalize(name): name for name in known}
            for match in _GIVEN_NAME_TOKEN.finditer(chunk.text):
                token = match.group(1)
                normalized = self._normalizer.normalize(token)
                if normalized not in by_normalized:
                    continue
                candidates.append(
                    EntityCandidate(
                        entity_type=EntityType.PERSON,
                        name=token,
                        normalized_name=normalized,
                        chunk_id=chunk.chunk_id,
                        start_offset=match.start(1),
                        end_offset=match.end(1),
                        confidence=self._scorer.score_given_name_candidate(),
                        source=self.name,
                        language_code=chunk.language_code,
                        subtype="given_name",
                        metadata=(("signal", "weak"),),
                    )
                )
        return candidates


__all__ = ["GivenNameRecognizer"]
