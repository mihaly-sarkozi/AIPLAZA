from __future__ import annotations

import re

from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType


class SystemNameRecognizer(BaseRecognizer):
    name = "system_name"
    version = "1.0"

    _DEFAULT_SYSTEMS = ("HubSpot", "CRM", "Salesforce", "SAP", "Jira", "Confluence")

    def __init__(self, systems: tuple[str, ...] | None = None) -> None:
        self._systems = systems or self._DEFAULT_SYSTEMS
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for system in self._systems:
                pattern = re.compile(rf"\b{re.escape(system)}\w*\b", re.IGNORECASE)
                for match in pattern.finditer(chunk.text):
                    candidates.append(
                        EntityCandidate(
                            entity_type=EntityType.SYSTEM,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(system),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=0.9,
                        )
                    )
        return candidates


class DictionaryEntityRecognizer(BaseRecognizer):
    name = "dictionary_entity"
    version = "1.0"

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for entry in context.entity_dictionary:
                name = str(entry.get("name") or "").strip()
                entity_type = EntityType(str(entry.get("type") or EntityType.OTHER.value))
                if not name:
                    continue
                pattern = re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)
                for match in pattern.finditer(chunk.text):
                    candidates.append(
                        EntityCandidate(
                            entity_type=entity_type,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(name),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=float(entry.get("confidence") or 0.8),
                        )
                    )
        return candidates


class ProductRecognizer(BaseRecognizer):
    name = "product"
    version = "1.0"

    _PRODUCTS = ("HubSpot",)

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for product in self._PRODUCTS:
                pattern = re.compile(rf"\b{re.escape(product)}\b", re.IGNORECASE)
                for match in pattern.finditer(chunk.text):
                    candidates.append(
                        EntityCandidate(
                            entity_type=EntityType.PRODUCT,
                            name=match.group(0),
                            normalized_name=self._normalizer.normalize(product),
                            chunk_id=chunk.chunk_id,
                            start_offset=match.start(),
                            end_offset=match.end(),
                            confidence=0.75,
                        )
                    )
        return candidates


__all__ = ["DictionaryEntityRecognizer", "ProductRecognizer", "SystemNameRecognizer"]
