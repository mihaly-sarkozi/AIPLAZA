from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.gazetteers.LegalFormGazetteer import LegalFormGazetteer


class LegalFormCompanyRecognizer(BaseRecognizer):
    name = "legal_form_company"
    version = "1.0"

    def __init__(self, gazetteer: LegalFormGazetteer | None = None) -> None:
        self._gazetteer = gazetteer or LegalFormGazetteer()
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            pattern = self._pattern_for_language(chunk.language_code)
            for match in pattern.finditer(chunk.text):
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

    def _pattern_for_language(self, language_code: str | None) -> re.Pattern[str]:
        suffixes = self._gazetteer.forms_for_language(language_code)
        escaped = sorted({re.escape(form) for form in suffixes}, key=len, reverse=True)
        suffix_group = "|".join(escaped)
        return re.compile(
            rf"\b([A-ZÁÉÍÓÖŐÚÜŰ0-9][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű.\-]{{0,100}}?\s(?:{suffix_group}))\b",
            re.UNICODE | re.IGNORECASE,
        )


__all__ = ["LegalFormCompanyRecognizer"]
