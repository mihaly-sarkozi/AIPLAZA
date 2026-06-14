from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter

logger = logging.getLogger(__name__)


class QdrantSearchAdapter:
    """Qdrant vector search — csak olvasás, indexing adapter kiterjesztése."""

    def __init__(self, qdrant_adapter: QdrantAdapter | None = None) -> None:
        self._qdrant = qdrant_adapter or QdrantAdapter()

    def collection_exists(self, collection_name: str) -> bool:
        return self._qdrant.collection_exists(collection_name)

    def get_collection_point_count(self, collection_name: str) -> int:
        try:
            info = self._qdrant.client.get_collection(collection_name)
            return int(getattr(info, "points_count", 0) or 0)
        except Exception:
            logger.warning("Qdrant point count lekérés sikertelen (%s)", collection_name, exc_info=True)
            return 0

    def search(
        self,
        *,
        collection_name: str,
        query_vector: list[float],
        top_k: int = 10,
        payload_filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        qdrant_filter = None
        if payload_filter:
            must = []
            for key, value in payload_filter.items():
                if value is None:
                    continue
                must.append(FieldCondition(key=key, match=MatchValue(value=value)))
            if must:
                qdrant_filter = Filter(must=must)

        try:
            hits = self._qdrant.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=max(1, int(top_k)),
                query_filter=qdrant_filter,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            logger.warning("Qdrant search hiba (%s): %s", collection_name, exc, exc_info=True)
            raise

        results: list[dict[str, Any]] = []
        for hit in hits or []:
            results.append(
                {
                    "qdrant_point_id": str(hit.id),
                    "score": float(hit.score or 0.0),
                    "payload": dict(hit.payload or {}),
                }
            )
        return results


__all__ = ["QdrantSearchAdapter"]
