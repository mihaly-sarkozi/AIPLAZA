from __future__ import annotations

from collections import defaultdict

from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto


class EntityChunkRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        entities: list[KnowledgeEntityDto] = kwargs.get("entities") or []
        rows: list[dict] = []
        for entity in entities:
            entity_key = f"{entity.entity_type.value}:{entity.normalized_name}"
            for chunk_id in entity.chunk_ids:
                rows.append(
                    {
                        "from_type": "entity",
                        "from_id": entity_key,
                        "to_type": "chunk",
                        "to_id": chunk_id,
                        "relation": "mentioned_in",
                        "confidence": entity.confidence,
                        "evidence_chunk_ids": [chunk_id],
                        "evidence_text": entity.name,
                        "weight": entity.confidence,
                    }
                )
            rows.append(
                {
                    "from_type": "entity",
                    "from_id": entity_key,
                    "to_type": "document",
                    "to_id": ctx.training_item_id,
                    "relation": "appears_in",
                    "confidence": entity.confidence,
                }
            )
        return rows


class EntityCoOccurrenceBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        entities: list[KnowledgeEntityDto] = kwargs.get("entities") or []
        chunk_entities: dict[str, list[KnowledgeEntityDto]] = defaultdict(list)
        for entity in entities:
            for chunk_id in entity.chunk_ids:
                chunk_entities[chunk_id].append(entity)
        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for co_occurring in chunk_entities.values():
            for index, first in enumerate(co_occurring):
                for second in co_occurring[index + 1 :]:
                    first_key = f"{first.entity_type.value}:{first.normalized_name}"
                    second_key = f"{second.entity_type.value}:{second.normalized_name}"
                    pair = tuple(sorted((first_key, second_key)))
                    if first_key == second_key or pair in seen:
                        continue
                    seen.add(pair)
                    rows.append(
                        {
                            "from_type": "entity",
                            "from_id": pair[0],
                            "to_type": "entity",
                            "to_id": pair[1],
                            "relation": "related_to",
                            "confidence": min(first.confidence, second.confidence),
                        }
                    )
        return rows


__all__ = ["EntityChunkRelationshipBuilder", "EntityCoOccurrenceBuilder"]
