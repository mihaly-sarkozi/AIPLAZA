from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VectorIndexPort(ABC):
    @abstractmethod
    async def ensure_collection_schema(self, collection: str) -> None:
        """Qdrant collection biztosítása."""
        ...

    @abstractmethod
    async def upsert_sentence_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Sentence pointok upsertje."""
        ...

    @abstractmethod
    async def upsert_structural_chunk_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Structural chunk pointok upsertje."""
        ...

    @abstractmethod
    async def upsert_assertion_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Assertion pointok upsertje."""
        ...

    @abstractmethod
    async def upsert_entity_points(self, collection: str, rows: list[dict[str, Any]]) -> None:
        """Entity pointok upsertje."""
        ...

    @abstractmethod
    async def search_points(
        self,
        collection: str,
        query: str,
        limit: int = 10,
        point_types: list[str] | None = None,
        payload_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Dense similarity keresés payload filterrel."""
        ...

    @abstractmethod
    async def delete_points_by_ids(self, collection: str, point_ids: list[str]) -> None:
        """Pontok törlése ID lista szerint."""
        ...

    @abstractmethod
    async def delete_points_by_source_point_id(self, collection: str, source_point_id: str) -> None:
        """Pontok törlése source_point_id szerint."""
        ...
