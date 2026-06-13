from __future__ import annotations

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer


class LegalFormCompanyRecognizer(BaseRecognizer):
    name = "legal_form_company"
    version = "1.1"

    def __init__(self, gazetteer: LegalFormGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or LegalFormGazetteer()
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            pattern = self._gazetteer.company_pattern_for_language(chunk.language_code)
            matches = self._longest_non_overlapping(pattern.finditer(chunk.text))
            for match in matches:
                name = match.group(1).strip(" ,;")
                if len(name) < 3:
                    continue
                candidates.append(
                    EntityCandidate(
                        entity_type=EntityType.COMPANY,
                        name=name,
                        normalized_name=self._normalizer.normalize(name),
                        chunk_id=chunk.chunk_id,
                        start_offset=match.start(1),
                        end_offset=match.end(1),
                        confidence=0.93,
                    )
                )
        return candidates

    @staticmethod
    def _longest_non_overlapping(
        matches: object,
    ) -> list[re.Match[str]]:
        ordered = sorted(
            list(matches),
            key=lambda match: (match.start(1), -(match.end(1) - match.start(1))),
        )
        kept: list[re.Match[str]] = []
        for match in ordered:
            start, end = match.start(1), match.end(1)
            if any(not (end <= other.start(1) or start >= other.end(1)) for other in kept):
                continue
            kept.append(match)
        return sorted(kept, key=lambda match: match.start(1))


__all__ = ["LegalFormCompanyRecognizer"]
