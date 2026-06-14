from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from apps.kb.kb_embedding.adapters.EmbeddingProviderPort import EmbeddingProviderPort
from apps.kb.kb_embedding.dto.EmbeddingGenerationOutputDto import (
    EmbeddingGenerationFailureDto,
    EmbeddingGenerationOutputDto,
)
from apps.kb.kb_embedding.dto.EmbeddingInputDto import EmbeddingInputDto
from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto
from apps.kb.kb_embedding.enums.EmbeddingErrorCode import EmbeddingErrorCode
from apps.kb.kb_embedding.errors.EmbeddingProcessingError import EmbeddingProcessingError
from apps.kb.kb_embedding.errors.LocalEmbeddingError import LocalEmbeddingError
from apps.kb.shared.hash_utils import vector_hash

logger = logging.getLogger(__name__)


class GenerateEmbeddingService:
    def __init__(
        self,
        provider: EmbeddingProviderPort,
        *,
        expected_dimension: int,
        batch_size: int = 16,
        record_event: Callable[[str, dict[str, Any] | None], None] | None = None,
        local_provider: bool = False,
    ) -> None:
        self._provider = provider
        self._expected_dimension = expected_dimension
        self._batch_size = max(1, int(batch_size))
        self._record_event = record_event
        self._local_provider = local_provider
        self._model_loaded = False

    def bind_local_events(
        self,
        flow_ctx,
        flow_recorder,
        *,
        module: str = "kb_embedding",
        stage: str = "EMBEDDING",
    ) -> None:
        if not self._local_provider:
            return

        def record(event_type: str, payload: dict[str, Any] | None = None) -> None:
            summary = dict(payload or {})
            duration_ms = int(summary.pop("duration_ms", 0) or 0)
            if event_type.endswith("_STARTED"):
                flow_recorder.record_stage_started(
                    flow_ctx,
                    module=module,
                    stage=stage,
                    step="GENERATE",
                    event_type=event_type,
                    input_summary_json=summary or None,
                )
            elif event_type.endswith("_FAILED"):
                flow_recorder.record_stage_failed(
                    flow_ctx,
                    module=module,
                    stage=stage,
                    step="GENERATE",
                    duration_ms=duration_ms,
                    message=str(summary.get("message") or summary.get("error_code") or event_type),
                    error_code=str(summary.get("error_code") or event_type),
                    input_summary_json=summary or None,
                )
                issue_code = str(summary.get("error_code") or event_type)
                flow_recorder.open_issue(
                    flow_ctx,
                    module=module,
                    stage=stage,
                    step="GENERATE",
                    severity="error",
                    issue_code=issue_code,
                    issue_message=str(summary.get("message") or issue_code),
                    metadata_json=summary or None,
                )
            else:
                flow_recorder.record_stage_completed(
                    flow_ctx,
                    module=module,
                    stage=stage,
                    step="GENERATE",
                    event_type=event_type,
                    duration_ms=duration_ms,
                    output_summary_json=summary or None,
                )

        self._record_event = record

    def generate(
        self,
        inputs: list[EmbeddingInputDto],
        *,
        model: str,
    ) -> EmbeddingGenerationOutputDto:
        if not inputs:
            return EmbeddingGenerationOutputDto()

        output = EmbeddingGenerationOutputDto()
        self._ensure_local_model_loaded(model)

        for offset in range(0, len(inputs), self._batch_size):
            batch = inputs[offset:offset + self._batch_size]
            batch_no = offset // self._batch_size + 1
            results_before = len(output.results)
            failures_before = len(output.failures)
            self._emit_local_event(
                "LOCAL_EMBEDDING_BATCH_STARTED",
                {"batch": batch_no, "size": len(batch)},
            )
            started = time.monotonic()
            try:
                texts = [item.input_text for item in batch]
                vectors = self._provider.embed_texts(texts, model)
                if len(vectors) != len(batch):
                    raise EmbeddingProcessingError(
                        EmbeddingErrorCode.EMBEDDING_PROVIDER_FAILED.value,
                        retryable=True,
                        detail="vector_count_mismatch",
                    )
                for item, vector in zip(batch, vectors, strict=True):
                    if not vector:
                        output.failures.append(
                            EmbeddingGenerationFailureDto(
                                chunk_id=item.chunk_id,
                                error_code=EmbeddingErrorCode.EMPTY_EMBEDDING_VECTOR.value,
                                error_message=EmbeddingErrorCode.EMPTY_EMBEDDING_VECTOR.value,
                            )
                        )
                        continue
                    if len(vector) != self._expected_dimension:
                        code = (
                            EmbeddingErrorCode.LOCAL_EMBEDDING_DIMENSION_MISMATCH.value
                            if self._local_provider
                            else EmbeddingErrorCode.EMBEDDING_DIMENSION_MISMATCH.value
                        )
                        output.failures.append(
                            EmbeddingGenerationFailureDto(
                                chunk_id=item.chunk_id,
                                error_code=code,
                                error_message=f"expected={self._expected_dimension}, actual={len(vector)}",
                            )
                        )
                        continue
                    output.results.append(
                        EmbeddingResultDto(
                            chunk_id=item.chunk_id,
                            vector=vector,
                            vector_hash=vector_hash(vector),
                            input_hash=item.input_hash,
                            content_hash=item.content_hash,
                            dimension=len(vector),
                        )
                    )
                self._emit_local_event(
                    "LOCAL_EMBEDDING_BATCH_COMPLETED",
                    {
                        "batch": batch_no,
                        "size": len(batch),
                        "duration_ms": int((time.monotonic() - started) * 1000),
                        "generated": len(output.results) - results_before,
                        "failed": len(output.failures) - failures_before,
                    },
                )
            except LocalEmbeddingError as exc:
                logger.exception("Local embedding batch hiba")
                self._emit_local_event(
                    "LOCAL_EMBEDDING_GENERATION_FAILED",
                    {"batch": batch_no, "error_code": exc.code, "message": exc.message},
                )
                for item in batch:
                    output.failures.append(
                        EmbeddingGenerationFailureDto(
                            chunk_id=item.chunk_id,
                            error_code=exc.code,
                            error_message=exc.message,
                        )
                    )
            except EmbeddingProcessingError as exc:
                logger.exception("Embedding provider hiba")
                code = str(exc.code)
                if self._local_provider:
                    self._emit_local_event(
                        "LOCAL_EMBEDDING_GENERATION_FAILED",
                        {"batch": batch_no, "error_code": code},
                    )
                for item in batch:
                    output.failures.append(
                        EmbeddingGenerationFailureDto(
                            chunk_id=item.chunk_id,
                            error_code=code,
                            error_message=str(exc),
                        )
                    )
            except Exception as exc:
                logger.exception("Embedding generation hiba")
                code = (
                    EmbeddingErrorCode.LOCAL_EMBEDDING_GENERATION_FAILED.value
                    if self._local_provider
                    else EmbeddingErrorCode.EMBEDDING_PROVIDER_FAILED.value
                )
                if self._local_provider:
                    self._emit_local_event(
                        "LOCAL_EMBEDDING_GENERATION_FAILED",
                        {"batch": batch_no, "error_code": code, "message": str(exc)},
                    )
                for item in batch:
                    output.failures.append(
                        EmbeddingGenerationFailureDto(
                            chunk_id=item.chunk_id,
                            error_code=code,
                            error_message=str(exc),
                        )
                    )

        if not output.results and output.failures:
            first = output.failures[0]
            if first.error_code == EmbeddingErrorCode.LOCAL_EMBEDDING_MODEL_LOAD_FAILED.value:
                raise EmbeddingProcessingError(
                    first.error_code,
                    retryable=True,
                    message=first.error_message,
                )
        return output

    def _ensure_local_model_loaded(self, model: str) -> None:
        if not self._local_provider or self._model_loaded:
            return
        ensure_loaded = getattr(self._provider, "ensure_model_loaded", None)
        if ensure_loaded is None:
            self._model_loaded = True
            return
        self._emit_local_event("LOCAL_EMBEDDING_MODEL_LOADING_STARTED", {"model": model})
        started = time.monotonic()
        try:
            ensure_loaded(model)
        except LocalEmbeddingError as exc:
            self._emit_local_event(
                "LOCAL_EMBEDDING_GENERATION_FAILED",
                {"error_code": exc.code, "message": exc.message},
            )
            raise EmbeddingProcessingError(
                exc.code,
                retryable=True,
                message=exc.message,
            ) from exc
        self._model_loaded = True
        self._emit_local_event(
            "LOCAL_EMBEDDING_MODEL_LOADING_COMPLETED",
            {"model": model, "duration_ms": int((time.monotonic() - started) * 1000)},
        )

    def _emit_local_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        if not self._local_provider or self._record_event is None:
            return
        self._record_event(event_type, payload)


__all__ = ["GenerateEmbeddingService"]
