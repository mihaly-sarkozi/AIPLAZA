from __future__ import annotations

from typing import Any

from apps.kb.kb_search.adapters.QdrantSearchAdapter import QdrantSearchAdapter
from core.kernel.config.config_loader import settings


class PayloadFilterService:
    def build_filter(
        self,
        *,
        knowledge_base_id: str,
        filters: dict[str, Any] | None = None,
        include_language: bool = True,
    ) -> dict[str, Any]:
        merged = {"knowledge_base_id": knowledge_base_id}
        for key, value in dict(filters or {}).items():
            if key == "channel_id":
                continue
            if key == "language_code" and not include_language:
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

    @staticmethod
    def _language_filter_mode() -> str:
        mode = str(getattr(settings, "kb_search_language_filter_mode", "soft") or "soft").strip().lower()
        if mode not in {"off", "soft", "strict"}:
            return "soft"
        return mode

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

        mode = self._language_filter_mode()
        raw_filters = dict(filters or {})
        preferred_language = raw_filters.get("language_code")

        if mode == "off":
            hits = self._search_once(
                collection=collection,
                knowledge_base_id=knowledge_base_id,
                query_vector=query_vector,
                top_k=top_k,
                filters=raw_filters,
                include_language=False,
            )
            return hits

        hits = self._search_once(
            collection=collection,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=top_k,
            filters=raw_filters,
            include_language=mode == "strict" or bool(preferred_language),
        )
        if hits or mode != "soft" or not preferred_language:
            return hits

        return self._search_once(
            collection=collection,
            knowledge_base_id=knowledge_base_id,
            query_vector=query_vector,
            top_k=top_k,
            filters=raw_filters,
            include_language=False,
        )

    def _search_once(
        self,
        *,
        collection: str,
        knowledge_base_id: str,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any],
        include_language: bool,
    ) -> list[dict[str, Any]]:
        payload_filter = self._payload_filter.build_filter(
            knowledge_base_id=knowledge_base_id,
            filters=filters,
            include_language=include_language,
        )
        return self._qdrant.search(
            collection_name=collection,
            query_vector=query_vector,
            top_k=top_k,
            payload_filter=payload_filter,
        )


__all__ = ["PayloadFilterService", "QdrantVectorSearchService"]
