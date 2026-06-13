from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import TemporalMentionDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto


class TemporalRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        entities: list[KnowledgeEntityDto] = kwargs.get("entities") or []
        temporal: list[TemporalMentionDto] = kwargs.get("temporal") or []
        rows: list[dict] = []
        for mention in temporal:
            rows.append(
                {
                    "from_type": "time",
                    "from_id": mention.raw_text.lower(),
                    "to_type": "chunk",
                    "to_id": mention.chunk_id,
                    "relation": "occurs_in",
                    "confidence": mention.confidence,
                }
            )
            for entity in entities:
                if mention.chunk_id in entity.chunk_ids:
                    entity_key = f"{entity.entity_type.value}:{entity.normalized_name}"
                    rows.append(
                        {
                            "from_type": "entity",
                            "from_id": entity_key,
                            "to_type": "time",
                            "to_id": mention.raw_text.lower(),
                            "relation": "associated_with",
                            "confidence": min(entity.confidence, mention.confidence),
                        }
                    )
        return rows


__all__ = ["TemporalRelationshipBuilder"]
