from __future__ import annotations

from typing import Any

from apps.kb.kb_search.adapters.QdrantSearchAdapter import QdrantSearchAdapter


class PayloadFilterService:
    def build_filter(
        self,
        *,
        knowledge_base_id: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        merged = {"knowledge_base_id": knowledge_base_id}
        for key, value in dict(filters or {}).items():
            if key == "channel_id":
                continue
            if value is not None and key not in merged:
                merged[key] = value
        return merged


class QdrantVectorSearchService:
    def __init__(
        self,
        *,
        qdrant_search: QdrantSearchAdapter,
        payload_filter_service: PayloadFilterService,
        knowledge_base_reader,
    ) -> None:
        self._qdrant = qdrant_search
        self._payload_filter = payload_filter_service
        self._kb_reader = knowledge_base_reader

    def search(
        self,
        *,
        knowledge_base_id: str,
        query_vector: list[float],
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        collection = self._kb_reader.get_qdrant_collection_name(knowledge_base_id)
        if not collection:
            return []
        payload_filter = self._payload_filter.build_filter(
            knowledge_base_id=knowledge_base_id,
            filters=filters,
        )
        return self._qdrant.search(
            collection_name=collection,
            query_vector=query_vector,
            top_k=top_k,
            payload_filter=payload_filter,
        )


__all__ = ["PayloadFilterService", "QdrantVectorSearchService"]
