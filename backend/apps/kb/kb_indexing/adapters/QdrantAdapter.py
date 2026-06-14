from __future__ import annotations

import logging
from typing import Any

from core.kernel.config.config_loader import settings

logger = logging.getLogger(__name__)


class QdrantAdapter:
    def __init__(self, client=None) -> None:
        if client is not None:
            self._client = client
            return
        from qdrant_client import QdrantClient

        url = str(settings.qdrant_url or "").strip()
        if not url:
            raise ValueError("Qdrant adapter: hiányzó qdrant_url")
        api_key = str(settings.qdrant_api_key or "").strip() or None
        timeout = int(settings.qdrant_timeout_sec or 120)
        self._client = QdrantClient(url=url, api_key=api_key, timeout=timeout)

    @property
    def client(self):
        return self._client

    def collection_exists(self, collection_name: str) -> bool:
        try:
            collections = self._client.get_collections().collections
            return any(col.name == collection_name for col in collections)
        except Exception:
            logger.warning("Qdrant collection_exists hiba (%s)", collection_name, exc_info=True)
            return False

    def get_collection_vector_size(self, collection_name: str) -> int | None:
        try:
            info = self._client.get_collection(collection_name)
            vectors = info.config.params.vectors
            if isinstance(vectors, dict):
                first = next(iter(vectors.values()))
                return int(first.size)
            return int(vectors.size)
        except Exception:
            logger.warning("Qdrant get_collection_vector_size hiba (%s)", collection_name, exc_info=True)
            return None

    def create_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance: str = "cosine",
    ) -> None:
        from qdrant_client.models import Distance, VectorParams

        distance_map = {
            "cosine": Distance.COSINE,
            "euclid": Distance.EUCLID,
            "dot": Distance.DOT,
        }
        self._client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size,
                distance=distance_map.get(distance, Distance.COSINE),
            ),
        )

    def upsert_points(
        self,
        collection_name: str,
        points: list[dict[str, Any]],
    ) -> None:
        from qdrant_client.models import PointStruct

        structs = [
            PointStruct(
                id=point["id"],
                vector=point["vector"],
                payload=point.get("payload") or {},
            )
            for point in points
        ]
        self._client.upsert(collection_name=collection_name, points=structs)


__all__ = ["QdrantAdapter"]
