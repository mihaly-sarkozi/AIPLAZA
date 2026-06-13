from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType


class CompanyNameRecognizer(BaseRecognizer):
    name = "company_name"
    version = "1.0"

    _PATTERN = re.compile(
        r"\b([A-ZÁÉÍÓÖŐÚÜŰ0-9][\wÁÉÍÓÖŐÚÜŰáéíóöőúüű.\-]{0,80}?\s(?:Kft\.|Bt\.|Zrt\.|Nyrt\.))",
        re.UNICODE,
    )

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for match in self._PATTERN.finditer(chunk.text):
                name = match.group(1).strip()
                candidates.append(
                    EntityCandidate(
                        entity_type=EntityType.COMPANY,
                        name=name,
                        normalized_name=self._normalizer.normalize(name),
                        chunk_id=chunk.chunk_id,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        confidence=0.95,
                    )
                )
        return candidates


__all__ = ["CompanyNameRecognizer"]
