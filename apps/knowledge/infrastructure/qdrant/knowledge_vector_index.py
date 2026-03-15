from __future__ import annotations

from typing import Any

from apps.core.qdrant.qdrant_wrapper import QdrantClientWrapper
from apps.knowledge.ports.vector_index_port import VectorIndexPort


class KnowledgeVectorIndex(VectorIndexPort):
    """Knowledge retrievalhez dedikált Qdrant adapter."""

    def __init__(self, qdrant: QdrantClientWrapper):
        self.qdrant = qdrant

    async def ensure_collection_schema(self, collection: str) -> None:
        """Kollekció séma biztosítása."""
        await self.qdrant.ensure_collection_schema_async(collection)

    async def upsert_sentence_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Sentence pontok upsertje."""
        await self.qdrant.upsert_sentence_points(collection, rows)

    async def upsert_structural_chunk_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Chunk pontok upsertje."""
        await self.qdrant.upsert_structural_chunk_points(collection, rows)

    async def upsert_assertion_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Assertion pontok upsertje."""
        await self.qdrant.upsert_assertion_points(collection, rows)

    async def upsert_entity_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Entity pontok upsertje."""
        await self.qdrant.upsert_entity_points(collection, rows)

    async def search_points(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Keresés payload filterrel."""
        return await self.qdrant.search_points_with_filters(
            collection=collection,
            query=query,
            limit=limit,
            point_types=point_types,
            payload_filter=payload_filter,
        )

    async def delete_points_by_ids(self, collection: str, point_ids: list[str]) -> None:
        """Pontok törlése id lista alapján."""
        await self.qdrant.delete_points_by_ids(collection, point_ids)

    async def delete_points_by_source_point_id(self, collection: str, source_point_id: str) -> None:
        """Pontok törlése source_point_id alapján."""
        await self.qdrant.delete_points_by_source_point_id(collection, source_point_id)
