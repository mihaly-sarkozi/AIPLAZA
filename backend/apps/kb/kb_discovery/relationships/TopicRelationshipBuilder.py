from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto


class TopicRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        topics: list[KnowledgeTopicDto] = kwargs.get("topics") or []
        rows: list[dict] = []
        seen: set[str] = set()
        for topic in topics:
            rows.append(
                {
                    "from_type": "topic",
                    "from_id": topic.topic_key,
                    "to_type": "chunk",
                    "to_id": topic.chunk_id,
                    "relation": "has_topic",
                    "confidence": topic.confidence,
                }
            )
            if topic.topic_key not in seen:
                seen.add(topic.topic_key)
                rows.append(
                    {
                        "from_type": "topic",
                        "from_id": topic.topic_key,
                        "to_type": "document",
                        "to_id": ctx.training_item_id,
                        "relation": "has_topic",
                        "confidence": topic.confidence,
                    }
                )
        return rows


__all__ = ["TopicRelationshipBuilder"]
