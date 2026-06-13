from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType


class IdentifierRecognizer(BaseRecognizer):
    name = "identifier"
    version = "1.0"

    _PATTERNS: tuple[tuple[EntityType, re.Pattern[str]], ...] = (
        (EntityType.EMAIL, re.compile(r"\b[\w.+-]+@[\w.-]+\.\w{2,}\b")),
        (EntityType.PHONE, re.compile(r"\b(?:\+36|06)[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{4}\b")),
        (EntityType.URL, re.compile(r"\bhttps?://[\w./?=&%-]+")),
        (EntityType.TICKET_ID, re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,6}\b")),
        (
            EntityType.CONTRACT_NUMBER,
            re.compile(r"\b(?:SZERZ|SZ|CTR|K)[-/]?\d{2,4}[-/]\d{1,6}\b", re.IGNORECASE),
        ),
        (
            EntityType.INVOICE_NUMBER,
            re.compile(r"\b(?:SZLA|INV)[-/]?\d{2,4}[-/]?\d{1,8}\b", re.IGNORECASE),
        ),
    )

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for entity_type, pattern in self._PATTERNS:
                for match in pattern.finditer(chunk.text):
                    name = match.group(0).strip()
                    candidates.append(
                        EntityCandidate(
                            entity_type=entity_type,
                            name=name,
                            normalized_name=self._normalizer.normalize(name),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=1.0,
                        )
                    )
        return candidates


__all__ = ["IdentifierRecognizer"]
