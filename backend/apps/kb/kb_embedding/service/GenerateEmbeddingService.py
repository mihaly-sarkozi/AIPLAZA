from __future__ import annotations

import logging

from apps.kb.kb_embedding.adapters.EmbeddingProviderPort import EmbeddingProviderPort
from apps.kb.kb_embedding.dto.EmbeddingInputDto import EmbeddingInputDto
from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto
from apps.kb.kb_embedding.enums.EmbeddingErrorCode import EmbeddingErrorCode
from apps.kb.kb_embedding.errors.EmbeddingProcessingError import EmbeddingProcessingError
from apps.kb.shared.hash_utils import vector_hash

logger = logging.getLogger(__name__)

_DEFAULT_BATCH_SIZE = 32


class GenerateEmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProviderPort,
        *,
        expected_dimension: int,
        batch_size: int = _DEFAULT_BATCH_SIZE,
    ) -> None:
        self._provider = provider
        self._expected_dimension = expected_dimension
        self._batch_size = max(1, int(batch_size))

    def generate(
        self,
        inputs: list[EmbeddingInputDto],
        *,
        model: str,
    ) -> list[EmbeddingResultDto]:
        results: list[EmbeddingResultDto] = []
        for offset in range(0, len(inputs), self._batch_size):
            batch = inputs[offset:offset + self._batch_size]
            texts = [item.input_text for item in batch]
            try:
                vectors = self._provider.embed_texts(texts, model)
            except Exception as exc:
                logger.exception("Embedding provider hiba")
                raise EmbeddingProcessingError(
                    EmbeddingErrorCode.EMBEDDING_PROVIDER_FAILED.value,
                    retryable=True,
                    message=str(exc),
                ) from exc
            if len(vectors) != len(batch):
                raise EmbeddingProcessingError(
                    EmbeddingErrorCode.EMBEDDING_PROVIDER_FAILED.value,
                    retryable=True,
                    detail="vector_count_mismatch",
                )
            for item, vector in zip(batch, vectors, strict=True):
                if not vector:
                    raise EmbeddingProcessingError(
                        EmbeddingErrorCode.EMPTY_EMBEDDING_VECTOR.value,
                        chunk_id=item.chunk_id,
                    )
                if len(vector) != self._expected_dimension:
                    raise EmbeddingProcessingError(
                        EmbeddingErrorCode.EMBEDDING_DIMENSION_MISMATCH.value,
                        chunk_id=item.chunk_id,
                        expected=self._expected_dimension,
                        actual=len(vector),
                    )
                results.append(
                    EmbeddingResultDto(
                        chunk_id=item.chunk_id,
                        vector=vector,
                        vector_hash=vector_hash(vector),
                        input_hash=item.input_hash,
                        content_hash=item.content_hash,
                        dimension=len(vector),
                    )
                )
        return results


__all__ = ["GenerateEmbeddingService"]
