from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.persons.PersonConfidenceScorer import PersonConfidenceScorer
from apps.kb.kb_discovery.persons.PersonDisambiguator import PersonDisambiguator


class PersonAliasRecognizer(BaseRecognizer):
    name = "person_alias"
    version = "1.0"

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()
        self._person_scorer = PersonConfidenceScorer()
        self._disambiguator = PersonDisambiguator()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        alias_map = self._build_alias_map(context.person_directory)
        if not alias_map:
            return []
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for alias, canonical in alias_map.items():
                pattern = re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)
                for match in pattern.finditer(chunk.text):
                    ambiguous = self._disambiguator.is_ambiguous(alias, alias_map)
                    candidates.append(
                        EntityCandidate(
                            entity_type=EntityType.PERSON,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(canonical),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=self._person_scorer.score(
                                directory_hit=True,
                                ambiguous=ambiguous,
                            ),
                            aliases=(alias,),
                        )
                    )
        return candidates

    def _build_alias_map(self, directory: list[dict]) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if not canonical:
                continue
            aliases = [canonical] + [str(a).strip() for a in (entry.get("aliases") or []) if str(a).strip()]
            for alias in aliases:
                key = self._normalizer.normalize(alias)
                if key:
                    alias_map[key] = canonical
        return alias_map


__all__ = ["PersonAliasRecognizer"]
