from __future__ import annotations

from apps.kb.kb_indexing.adapters.QdrantCollectionManager import QdrantCollectionManager
from apps.kb.kb_indexing.adapters.QdrantConfigValidator import QdrantConfigValidator
from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError


class EnsureQdrantCollectionService:
    def __init__(self, collection_manager: QdrantCollectionManager) -> None:
        self._collection_manager = collection_manager

    def ensure(
        self,
        collection_name: str,
        *,
        vector_size: int,
        distance_metric: str = "cosine",
    ) -> None:
        try:
            self._collection_manager.ensure_collection(
                collection_name,
                vector_size=vector_size,
                distance_metric=distance_metric,
            )
        except ValueError as exc:
            raise IndexingProcessingError(
                IndexingErrorCode.QDRANT_DIMENSION_MISMATCH.value,
                message=str(exc),
            ) from exc
        except IndexingProcessingError:
            raise
        except Exception as exc:
            message = str(exc)
            if not QdrantConfigValidator.is_configured():
                raise IndexingProcessingError(
                    IndexingErrorCode.QDRANT_CONFIG_MISSING.value,
                    message=message,
                ) from exc
            raise IndexingProcessingError(
                IndexingErrorCode.QDRANT_COLLECTION_MISSING.value,
                message=message,
                retryable=True,
            ) from exc


__all__ = ["EnsureQdrantCollectionService"]
