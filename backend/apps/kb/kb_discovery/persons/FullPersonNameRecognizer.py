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
from apps.kb.kb_discovery.persons.PersonContextSignals import PersonContextSignals

_NAME_PAIR = re.compile(
    r"\b([A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{1,})\s+"
    r"([A-ZÁÉÍÓÖŐÚÜŰ][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{1,})\b",
    re.UNICODE,
)


class FullPersonNameRecognizer(BaseRecognizer):
    """Két tagú személynév — given name gazetteer + family name minta."""

    name = "full_person_name"
    version = "1.0"

    def __init__(
        self,
        gazetteer: GivenNameGazetteer | None = None,
        context_signals: PersonContextSignals | None = None,
    ) -> None:
        self._gazetteer = gazetteer or GivenNameGazetteer()
        self._normalizer = TextNormalizer()
        self._scorer = PersonConfidenceScorer()
        self._context_signals = context_signals or PersonContextSignals()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        directory_names = self._directory_normalized_names(context.person_directory)
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            known = self._gazetteer.names_for(chunk.language_code)
            if not known:
                continue
            given_names = {self._normalizer.normalize(name) for name in known}
            for match in _NAME_PAIR.finditer(chunk.text):
                token1 = match.group(1)
                token2 = match.group(2)
                norm1 = self._normalizer.normalize(token1)
                norm2 = self._normalizer.normalize(token2)
                given_first = norm1 in given_names
                given_second = norm2 in given_names
                if not given_first and not given_second:
                    continue
                if given_first and given_second:
                    display_name = f"{token1} {token2}"
                    normalized = self._normalizer.normalize(display_name)
                elif given_first:
                    display_name = f"{token1} {token2}"
                    normalized = self._normalizer.normalize(f"{norm1} {norm2}")
                else:
                    display_name = f"{token2} {token1}"
                    normalized = self._normalizer.normalize(f"{norm2} {norm1}")
                directory_hit = normalized in directory_names or self._matches_directory_alias(
                    context.person_directory,
                    token1,
                    token2,
                )
                start = match.start(1)
                end = match.end(2)
                confidence = self._scorer.score_full_name(
                    directory_hit=directory_hit,
                    email_nearby=self._context_signals.email_nearby(chunk.text, start, end),
                    signature_nearby=self._context_signals.signature_nearby(chunk.text, start, end),
                )
                candidates.append(
                    EntityCandidate(
                        entity_type=EntityType.PERSON,
                        name=display_name,
                        normalized_name=normalized,
                        chunk_id=chunk.chunk_id,
                        start_offset=start,
                        end_offset=end,
                        confidence=confidence,
                        source=self.name,
                        language_code=chunk.language_code,
                        subtype="full_name",
                        metadata=(
                            ("given_name_token", token1 if given_first else token2),
                            ("family_name_token", token2 if given_first else token1),
                            ("directory_hit", directory_hit),
                        ),
                    )
                )
        return candidates

    @staticmethod
    def _directory_normalized_names(directory: list[dict]) -> set[str]:
        normalizer = TextNormalizer()
        names: set[str] = set()
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if canonical:
                names.add(normalizer.normalize(canonical))
        return names

    @staticmethod
    def _matches_directory_alias(directory: list[dict], token1: str, token2: str) -> bool:
        normalizer = TextNormalizer()
        pair_a = normalizer.normalize(f"{token1} {token2}")
        pair_b = normalizer.normalize(f"{token2} {token1}")
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if not canonical:
                continue
            normalized = normalizer.normalize(canonical)
            if normalized in {pair_a, pair_b}:
                return True
            aliases = [str(alias).strip() for alias in (entry.get("aliases") or []) if str(alias).strip()]
            alias_norms = {normalizer.normalize(alias) for alias in aliases}
            if token1 in aliases and token2 in aliases:
                return True
            if alias_norms.intersection({normalizer.normalize(token1), normalizer.normalize(token2)}):
                if normalized in {pair_a, pair_b}:
                    return True
        return False


__all__ = ["FullPersonNameRecognizer"]
