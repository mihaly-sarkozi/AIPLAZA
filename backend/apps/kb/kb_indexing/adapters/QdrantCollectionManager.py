from __future__ import annotations

import logging

from qdrant_client.models import PayloadSchemaType

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter

logger = logging.getLogger(__name__)

_PAYLOAD_INDEX_SCHEMA: dict[str, PayloadSchemaType] = {
    "knowledge_base_id": PayloadSchemaType.KEYWORD,
    "training_item_id": PayloadSchemaType.KEYWORD,
    "language_code": PayloadSchemaType.KEYWORD,
    "content_type": PayloadSchemaType.KEYWORD,
    "topics": PayloadSchemaType.KEYWORD,
    "entities": PayloadSchemaType.KEYWORD,
    "overall_score": PayloadSchemaType.FLOAT,
    "created_at": PayloadSchemaType.DATETIME,
    "updated_at": PayloadSchemaType.DATETIME,
}


class QdrantCollectionManager:
    def __init__(self, qdrant_adapter: QdrantAdapter) -> None:
        self._qdrant = qdrant_adapter

    def ensure_collection(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance_metric: str = "cosine",
    ) -> None:
        if not self._qdrant.collection_exists(collection_name):
            self._qdrant.create_collection(
                collection_name,
                vector_size=vector_size,
                distance=distance_metric,
            )
            logger.info("Qdrant collection létrehozva: %s (size=%s)", collection_name, vector_size)
        existing_size = self._qdrant.get_collection_vector_size(collection_name)
        if existing_size is not None and existing_size != vector_size:
            raise ValueError(
                f"Qdrant dimension mismatch: collection={collection_name} "
                f"expected={vector_size} actual={existing_size}"
            )
        self._ensure_payload_indexes(collection_name)

    def _ensure_payload_indexes(self, collection_name: str) -> None:
        client = self._qdrant.client
        for field, schema in _PAYLOAD_INDEX_SCHEMA.items():
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception:
                logger.debug(
                    "Qdrant payload index skip/már létezik: %s.%s",
                    collection_name,
                    field,
                    exc_info=True,
                )


__all__ = ["QdrantCollectionManager"]
