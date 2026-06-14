from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_indexing.dto.QdrantDeleteResult import QdrantDeleteResult

from apps.kb.kb_indexing.adapters.QdrantClientFactory import QdrantClientFactory

logger = logging.getLogger(__name__)


class QdrantAdapter:
    """Qdrant wrapper lazy client inicializációval."""

    def __init__(self, client=None, *, client_factory: QdrantClientFactory | None = None) -> None:
        self._client = client
        self._client_factory = client_factory or QdrantClientFactory()

    @property
    def client(self):
        if self._client is None:
            self._client = self._client_factory.create_client()
        return self._client

    def collection_exists(self, collection_name: str) -> bool:
        try:
            collections = self.client.get_collections().collections
            return any(col.name == collection_name for col in collections)
        except Exception:
            logger.warning("Qdrant collection_exists hiba (%s)", collection_name, exc_info=True)
            return False

    def get_collection_vector_size(self, collection_name: str) -> int | None:
        try:
            info = self.client.get_collection(collection_name)
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
        self.client.create_collection(
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
        self.client.upsert(collection_name=collection_name, points=structs)

    def retrieve_points(
        self,
        collection_name: str,
        point_ids: list[str],
        *,
        with_vectors: bool = True,
        with_payload: bool = True,
    ) -> list[dict[str, Any]]:
        if not point_ids:
            return []
        records = self.client.retrieve(
            collection_name=collection_name,
            ids=point_ids,
            with_vectors=with_vectors,
            with_payload=with_payload,
        )
        results: list[dict[str, Any]] = []
        for record in records:
            vector = record.vector
            if isinstance(vector, dict):
                vector = next(iter(vector.values()), None)
            results.append(
                {
                    "id": str(record.id),
                    "vector": vector,
                    "payload": dict(record.payload or {}),
                }
            )
        return results

    def delete_points(self, collection_name: str, point_ids: list[str]) -> QdrantDeleteResult:
        if not point_ids:
            return QdrantDeleteResult()
        from qdrant_client.models import PointIdsList

        requested = len(point_ids)
        try:
            self.client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids),
            )
            return QdrantDeleteResult(requested=requested, deleted=requested)
        except Exception as exc:
            logger.warning("Qdrant delete_points hiba (%s): %s", collection_name, exc, exc_info=True)
            missing = 0
            deleted = 0
            failed: list[str] = []
            for point_id in point_ids:
                try:
                    found = self.retrieve_points(collection_name, [point_id], with_vectors=False, with_payload=False)
                    if not found:
                        missing += 1
                        continue
                    self.client.delete(
                        collection_name=collection_name,
                        points_selector=PointIdsList(points=[point_id]),
                    )
                    deleted += 1
                except Exception:
                    failed.append(str(point_id))
            return QdrantDeleteResult(
                requested=requested,
                deleted=deleted,
                missing=missing,
                failed_ids=tuple(failed),
            )

    def delete_collection(self, collection_name: str) -> bool:
        name = str(collection_name or "").strip()
        if not name:
            return False
        if not self.collection_exists(name):
            return False
        try:
            self.client.delete_collection(collection_name=name)
            logger.info("Qdrant collection törölve: %s", name)
            return True
        except Exception:
            logger.warning("Qdrant collection törlés sikertelen: %s", name, exc_info=True)
            return False


__all__ = ["QdrantAdapter"]
