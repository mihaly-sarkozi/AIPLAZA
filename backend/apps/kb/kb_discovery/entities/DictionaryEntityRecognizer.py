from __future__ import annotations

import re

from apps.kb.kb_discovery.common.AccentPatternBuilder import accent_insensitive_pattern
from apps.kb.kb_discovery.common.BaseRecognizer import BaseRecognizer
from apps.kb.kb_discovery.common.DiscoveryContext import DiscoveryContext
from apps.kb.kb_discovery.common.EntityCandidate import EntityCandidate
from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enums.EntityType import EntityType
from apps.kb.kb_discovery.entities.entity_type_resolver import resolve_entity_type
from apps.kb.kb_discovery.gazetteers.SystemsGazetteer import SystemsGazetteer


class SystemNameRecognizer(BaseRecognizer):
    name = "system_name"
    version = "1.1"

    def __init__(self, systems_gazetteer: SystemsGazetteer | None = None) -> None:
        self._systems_gazetteer = systems_gazetteer or SystemsGazetteer()
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        systems = self._systems_gazetteer.systems_for(
            tenant_slug=context.tenant_slug,
            knowledge_base_id=context.knowledge_base_id,
        )
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for system in systems:
                pattern = accent_insensitive_pattern(system)
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
                            source=self.name,
                            language_code=chunk.language_code,
                            subtype="system_name",
                        )
                    )
        return candidates


class DictionaryEntityRecognizer(BaseRecognizer):
    name = "dictionary_entity"
    version = "1.1"

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def recognize(
        self, chunks: list[DiscoveryChunkDto], context: DiscoveryContext
    ) -> list[EntityCandidate]:
        candidates: list[EntityCandidate] = []
        for chunk in chunks:
            for entry in context.entity_dictionary:
                entry_name = str(entry.get("name") or "").strip()
                names = [entry_name] if entry_name else []
                names.extend(
                    str(alias).strip() for alias in (entry.get("aliases") or []) if str(alias).strip()
                )
                entity_type = resolve_entity_type(
                    entry.get("type"),
                    entry_name=entry_name or "unknown",
                    context=context,
                )
                confidence = float(entry.get("confidence") or 0.8)
                for name in dict.fromkeys(names):
                    if not name:
                        continue
                    pattern = accent_insensitive_pattern(name)
                    for match in pattern.finditer(chunk.text):
                        candidates.append(
                            EntityCandidate(
                                entity_type=entity_type,
                                name=match.group(0),
                                normalized_name=self._normalizer.normalize(
                                    str(entry.get("name") or name)
                                ),
                                chunk_id=chunk.chunk_id,
                                start_offset=match.start(),
                                end_offset=match.end(),
                                confidence=confidence,
                                source=self.name,
                                language_code=chunk.language_code,
                                subtype="dictionary",
                                metadata=(("dictionary_entry", entry_name),),
                            )
                        )
        return candidates


__all__ = ["DictionaryEntityRecognizer", "SystemNameRecognizer"]
