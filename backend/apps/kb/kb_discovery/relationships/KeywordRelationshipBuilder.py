from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeKeywordDto


class KeywordRelationshipBuilder:
    def build(self, ctx, **kwargs) -> list[dict]:
        keywords: list[KnowledgeKeywordDto] = kwargs.get("keywords") or []
        rows: list[dict] = []
        for keyword in keywords:
            rows.append(
                {
                    "from_type": "keyword",
                    "from_id": keyword.normalized_term,
                    "to_type": "chunk",
                    "to_id": keyword.chunk_id,
                    "relation": "has_keyword",
                    "confidence": keyword.confidence,
                }
            )
        return rows


__all__ = ["KeywordRelationshipBuilder"]
