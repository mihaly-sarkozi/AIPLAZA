from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto

_ENTITY_PREVIEW_LIMIT = 30


def build_entity_extraction_output_summary(
    entities: list[KnowledgeEntityDto],
    mentions: list[Any],
) -> dict[str, Any]:
    top_entities = sorted(entities, key=lambda entity: entity.confidence, reverse=True)[
        :_ENTITY_PREVIEW_LIMIT
    ]
    return {
        "entity_count": len(entities),
        "mention_count": len(mentions),
        "entities": [
            {
                "name": entity.name,
                "type": entity.entity_type.value,
                "confidence": round(entity.confidence, 4),
            }
            for entity in top_entities
        ],
    }


__all__ = ["build_entity_extraction_output_summary"]
