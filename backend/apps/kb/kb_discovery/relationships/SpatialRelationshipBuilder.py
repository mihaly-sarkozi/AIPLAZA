from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import SpatialMentionDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto


class SpatialRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        entities: list[KnowledgeEntityDto] = kwargs.get("entities") or []
        spatial: list[SpatialMentionDto] = kwargs.get("spatial") or []
        rows: list[dict] = []
        for mention in spatial:
            rows.append(
                {
                    "from_type": "location",
                    "from_id": mention.normalized_location,
                    "to_type": "chunk",
                    "to_id": mention.chunk_id,
                    "relation": "located_in",
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
                            "to_type": "location",
                            "to_id": mention.normalized_location,
                            "relation": "located_at",
                            "confidence": min(entity.confidence, mention.confidence),
                        }
                    )
        return rows


__all__ = ["SpatialRelationshipBuilder"]
