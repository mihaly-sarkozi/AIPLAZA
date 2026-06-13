from __future__ import annotations

from collections import defaultdict

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto, ProcessMentionDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto


class ProcessRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        process_mentions: list[ProcessMentionDto] = kwargs.get("process_mentions") or []
        temporal = kwargs.get("temporal") or []
        spatial = kwargs.get("spatial") or []
        rows: list[dict] = []
        for mention in process_mentions:
            process_id = mention.process_name or mention.step_text
            rows.append(
                {
                    "from_type": "process",
                    "from_id": process_id,
                    "to_type": "chunk",
                    "to_id": mention.chunk_id,
                    "relation": "has_step",
                    "confidence": mention.confidence,
                }
            )
            if mention.responsibility:
                rows.append(
                    {
                        "from_type": "person",
                        "from_id": mention.responsibility.lower(),
                        "to_type": "process",
                        "to_id": process_id,
                        "relation": "responsible_for",
                        "confidence": mention.confidence,
                    }
                )
            for time_mention in temporal:
                if time_mention.chunk_id == mention.chunk_id:
                    rows.append(
                        {
                            "from_type": "time",
                            "from_id": time_mention.raw_text.lower(),
                            "to_type": "process",
                            "to_id": process_id,
                            "relation": "occurs_in",
                            "confidence": min(time_mention.confidence, mention.confidence),
                        }
                    )
            for spatial_mention in spatial:
                if spatial_mention.chunk_id == mention.chunk_id:
                    rows.append(
                        {
                            "from_type": "location",
                            "from_id": spatial_mention.normalized_location,
                            "to_type": "process",
                            "to_id": process_id,
                            "relation": "located_in",
                            "confidence": min(spatial_mention.confidence, mention.confidence),
                        }
                    )
        return rows


class EntityTopicRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        entities: list[KnowledgeEntityDto] = kwargs.get("entities") or []
        topics: list[KnowledgeTopicDto] = kwargs.get("topics") or []
        topics_by_chunk: dict[str, list[KnowledgeTopicDto]] = defaultdict(list)
        for topic in topics:
            topics_by_chunk[topic.chunk_id].append(topic)

        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for entity in entities:
            entity_key = f"{entity.entity_type.value}:{entity.normalized_name}"
            for chunk_id in entity.chunk_ids:
                for topic in topics_by_chunk.get(chunk_id, []):
                    pair = (entity_key, topic.topic_key)
                    if pair in seen:
                        continue
                    seen.add(pair)
                    rows.append(
                        {
                            "from_type": "entity",
                            "from_id": entity_key,
                            "to_type": "topic",
                            "to_id": topic.topic_key,
                            "relation": "related_to",
                            "confidence": min(entity.confidence, topic.confidence),
                        }
                    )
        return rows


__all__ = ["EntityTopicRelationshipBuilder", "ProcessRelationshipBuilder"]
