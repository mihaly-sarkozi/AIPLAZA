from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from apps.kb.kb_embedding.dto.EmbeddingChunkDto import EmbeddingChunkDto
from apps.kb.kb_embedding.dto.EmbeddingInputDto import EmbeddingInputDto
from apps.kb.kb_embedding.dto.EmbeddingJobContext import EmbeddingJobContext
from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto
from apps.kb.kb_embedding.enums.EmbeddingErrorCode import EmbeddingErrorCode
from apps.kb.kb_embedding.enums.EmbeddingStatus import EmbeddingStatus
from apps.kb.kb_embedding.errors.EmbeddingProcessingError import EmbeddingProcessingError
from apps.kb.kb_embedding.events.indexing_requested_event import add_indexing_requested_event
from apps.kb.kb_embedding.ports.reader_ports import DiscoveryBundleReaderPort
from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository
from apps.kb.kb_embedding.service.BuildEmbeddingInputService import BuildEmbeddingInputService
from apps.kb.kb_embedding.service.GenerateEmbeddingService import GenerateEmbeddingService
from apps.kb.kb_embedding.service.StoreEmbeddingService import StoreEmbeddingService
from apps.kb.kb_embedding.service.ValidateEmbeddingService import ValidateEmbeddingService
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder, ProcessingFlowContext

logger = logging.getLogger(__name__)

_PROCESSING_MODULE = "kb_embedding"


class EmbeddingPipelineService:
    def __init__(
        self,
        job_repository: EmbeddingJobRepository,
        embedding_repository: KnowledgeEmbeddingRepository,
        bundle_reader: DiscoveryBundleReaderPort,
        build_input_service: BuildEmbeddingInputService,
        generate_service: GenerateEmbeddingService,
        store_service: StoreEmbeddingService,
        validate_service: ValidateEmbeddingService,
        *,
        embedding_model: str,
        embedding_provider: str,
        embedding_dimension: int,
        embedding_batch_size: int = 16,
        embedding_device: str = "cpu",
        embedding_normalize: bool = True,
        provider_metadata: dict | None = None,
        flow_recorder=None,
        emit_indexing_requested: Callable[..., None] = add_indexing_requested_event,
    ) -> None:
        self._job_repository = job_repository
        self._embedding_repository = embedding_repository
        self._bundle_reader = bundle_reader
        self._build_input_service = build_input_service
        self._generate_service = generate_service
        self._store_service = store_service
        self._validate_service = validate_service
        self.embedding_model = embedding_model
        self.embedding_provider = embedding_provider
        self.embedding_dimension = embedding_dimension
        self.embedding_batch_size = embedding_batch_size
        self.embedding_device = embedding_device
        self.embedding_normalize = embedding_normalize
        self._provider_metadata = dict(provider_metadata or {})
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()
        self._emit_indexing_requested = emit_indexing_requested

    def run(self, ctx: EmbeddingJobContext, chunks: list[EmbeddingChunkDto]) -> EmbeddingStatus:
        flow_ctx = ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug,
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )
        self._job_repository.set_status(ctx.job_id, EmbeddingStatus.RUNNING)
        self._flow_recorder.record_stage_started(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="EMBEDDING",
            step="PIPELINE",
            event_type="EMBEDDING_STARTED",
            input_summary_json={"chunks": len(chunks)},
        )
        started = time.monotonic()

        chunk_ids = [chunk.chunk_id for chunk in chunks]
        bundles = self._bundle_reader.get_bundles_for_chunks(
            ctx.discovery_job_id,
            ctx.training_item_id,
            chunk_ids,
        )

        inputs_to_generate: list[EmbeddingInputDto] = []
        skipped_results: list[EmbeddingResultDto] = []
        input_by_chunk: dict[str, EmbeddingInputDto] = {}

        for chunk in chunks:
            bundle = bundles.get(chunk.chunk_id)
            if bundle is not None:
                bundle = self._build_input_service.select_bundle_fields(bundle)
            built = self._build_input_service.build(chunk, bundle, title=ctx.title)
            input_by_chunk[chunk.chunk_id] = built
            existing = self._embedding_repository.find_existing(
                knowledge_base_id=ctx.knowledge_base_id,
                training_item_id=ctx.training_item_id,
                chunk_id=chunk.chunk_id,
                embedding_model=self.embedding_model,
                embedding_input_hash=built.input_hash,
            )
            if existing is not None and existing.embedding_vector:
                skipped_results.append(
                    EmbeddingResultDto(
                        chunk_id=chunk.chunk_id,
                        vector=list(existing.embedding_vector),
                        vector_hash=str(existing.vector_hash or ""),
                        input_hash=built.input_hash,
                        content_hash=built.content_hash,
                        dimension=int(existing.embedding_dimension or self.embedding_dimension),
                        skipped=True,
                    )
                )
                self._store_service.store_results(
                    tenant_slug=ctx.tenant_slug,
                    knowledge_base_id=ctx.knowledge_base_id,
                    training_item_id=ctx.training_item_id,
                    discovery_job_id=ctx.discovery_job_id,
                    embedding_job_id=ctx.job_id,
                    embedding_provider=self.embedding_provider,
                    embedding_model=self.embedding_model,
                    results=[skipped_results[-1]],
                )
            else:
                inputs_to_generate.append(built)

        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="EMBEDDING",
            step="BUILD_INPUT",
            event_type="EMBEDDING_INPUT_BUILT",
            duration_ms=0,
            output_summary_json={
                "to_generate": len(inputs_to_generate),
                "skipped": len(skipped_results),
            },
        )

        generated: list[EmbeddingResultDto] = []
        failed_chunks = 0
        store_metadata = self._build_store_metadata()
        if inputs_to_generate:
            self._generate_service.bind_local_events(flow_ctx, self._flow_recorder)
            try:
                generation = self._generate_service.generate(
                    inputs_to_generate,
                    model=self.embedding_model,
                )
                generated = generation.results
                if generated:
                    self._store_service.store_results(
                        tenant_slug=ctx.tenant_slug,
                        knowledge_base_id=ctx.knowledge_base_id,
                        training_item_id=ctx.training_item_id,
                        discovery_job_id=ctx.discovery_job_id,
                        embedding_job_id=ctx.job_id,
                        embedding_provider=self.embedding_provider,
                        embedding_model=self.embedding_model,
                        results=generated,
                        metadata=store_metadata,
                    )
                for failure in generation.failures:
                    input_item = input_by_chunk.get(failure.chunk_id)
                    self._store_service.store_failure(
                        tenant_slug=ctx.tenant_slug,
                        knowledge_base_id=ctx.knowledge_base_id,
                        training_item_id=ctx.training_item_id,
                        chunk_id=failure.chunk_id,
                        discovery_job_id=ctx.discovery_job_id,
                        embedding_job_id=ctx.job_id,
                        embedding_provider=self.embedding_provider,
                        embedding_model=self.embedding_model,
                        embedding_dimension=self.embedding_dimension,
                        error_code=failure.error_code,
                        error_message=failure.error_message,
                        content_hash=input_item.content_hash if input_item else None,
                        embedding_input_hash=input_item.input_hash if input_item else None,
                        metadata=store_metadata,
                    )
                    failed_chunks += 1
                    self._flow_recorder.open_issue(
                        flow_ctx,
                        module=_PROCESSING_MODULE,
                        stage="EMBEDDING",
                        step="GENERATE",
                        severity="error",
                        issue_code=failure.error_code,
                        issue_message=failure.error_message,
                    )
            except EmbeddingProcessingError as exc:
                for item in inputs_to_generate:
                    self._store_service.store_failure(
                        tenant_slug=ctx.tenant_slug,
                        knowledge_base_id=ctx.knowledge_base_id,
                        training_item_id=ctx.training_item_id,
                        chunk_id=item.chunk_id,
                        discovery_job_id=ctx.discovery_job_id,
                        embedding_job_id=ctx.job_id,
                        embedding_provider=self.embedding_provider,
                        embedding_model=self.embedding_model,
                        embedding_dimension=self.embedding_dimension,
                        error_code=str(exc.code),
                        error_message=str(exc),
                        content_hash=item.content_hash,
                        embedding_input_hash=item.input_hash,
                        metadata=store_metadata,
                    )
                    failed_chunks += 1
                self._flow_recorder.open_issue(
                    flow_ctx,
                    module=_PROCESSING_MODULE,
                    stage="EMBEDDING",
                    step="GENERATE",
                    severity="error",
                    issue_code=str(exc.code),
                    issue_message=str(exc),
                )
            except Exception as exc:
                logger.exception("Embedding generation hiba")
                error_code = (
                    EmbeddingErrorCode.LOCAL_EMBEDDING_GENERATION_FAILED.value
                    if self.embedding_provider == "local"
                    else EmbeddingErrorCode.EMBEDDING_PROVIDER_FAILED.value
                )
                for item in inputs_to_generate:
                    self._store_service.store_failure(
                        tenant_slug=ctx.tenant_slug,
                        knowledge_base_id=ctx.knowledge_base_id,
                        training_item_id=ctx.training_item_id,
                        chunk_id=item.chunk_id,
                        discovery_job_id=ctx.discovery_job_id,
                        embedding_job_id=ctx.job_id,
                        embedding_provider=self.embedding_provider,
                        embedding_model=self.embedding_model,
                        embedding_dimension=self.embedding_dimension,
                        error_code=error_code,
                        error_message=str(exc),
                        content_hash=item.content_hash,
                        embedding_input_hash=item.input_hash,
                        metadata=store_metadata,
                    )
                    failed_chunks += 1
                self._flow_recorder.open_issue(
                    flow_ctx,
                    module=_PROCESSING_MODULE,
                    stage="EMBEDDING",
                    step="GENERATE",
                    severity="error",
                    issue_code=error_code,
                    issue_message=str(exc),
                )

        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="EMBEDDING",
            step="GENERATE",
            event_type="EMBEDDING_GENERATION_COMPLETED",
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary_json={"generated": len(generated), "failed": failed_chunks},
        )

        all_results = skipped_results + generated
        counts = self._embedding_repository.count_by_status(ctx.job_id)
        embedded = counts.get("COMPLETED", 0)
        failed = counts.get("FAILED", 0)
        self._job_repository.update_progress(
            ctx.job_id,
            chunks_embedded=embedded,
            chunks_failed=failed,
        )

        valid, validation_issues = self._validate_service.validate(
            ctx.job_id,
            expected_dimension=self.embedding_dimension,
            chunk_ids=chunk_ids,
            results=all_results,
        )

        if embedded == 0:
            status = EmbeddingStatus.FAILED
            self._finish_job(ctx, flow_ctx, status, started, validation_issues)
            return status

        if failed > 0 or validation_issues:
            status = EmbeddingStatus.PARTIAL
        else:
            status = EmbeddingStatus.COMPLETED

        self._finish_job(ctx, flow_ctx, status, started, validation_issues)

        if status in (EmbeddingStatus.COMPLETED, EmbeddingStatus.PARTIAL) and embedded > 0:
            self._safe_emit(
                self._emit_indexing_requested,
                tenant_slug=ctx.tenant_slug,
                knowledge_base_id=ctx.knowledge_base_id,
                training_item_id=ctx.training_item_id,
                understanding_job_id=ctx.understanding_job_id,
                discovery_job_id=ctx.discovery_job_id,
                embedding_job_id=ctx.job_id,
                created_by=ctx.created_by,
            )

        return status

    def _finish_job(
        self,
        ctx: EmbeddingJobContext,
        flow_ctx: ProcessingFlowContext,
        status: EmbeddingStatus,
        started: float,
        issues: list[str],
    ) -> None:
        error_code = issues[0] if issues and status != EmbeddingStatus.COMPLETED else None
        self._job_repository.mark_finished(
            ctx.job_id,
            status,
            error_code=error_code,
            error_message=", ".join(issues) if issues else None,
        )
        event_type = "EMBEDDING_COMPLETED" if status == EmbeddingStatus.COMPLETED else "EMBEDDING_FAILED"
        if status == EmbeddingStatus.PARTIAL:
            event_type = "EMBEDDING_COMPLETED"
        self._flow_recorder.record_stage_completed(
            flow_ctx,
            module=_PROCESSING_MODULE,
            stage="EMBEDDING",
            step="PIPELINE",
            event_type=event_type,
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary_json={"status": status.value, "issues": issues},
        )
        if issues:
            for issue in issues:
                self._flow_recorder.open_issue(
                    flow_ctx,
                    module=_PROCESSING_MODULE,
                    stage="EMBEDDING",
                    step="VALIDATION",
                    severity="warning",
                    issue_code=issue,
                )
        self._flow_recorder.recalculate_metrics(flow_ctx)

    def _build_store_metadata(self) -> dict[str, Any]:
        metadata = {
            "provider": self.embedding_provider,
            "model": self.embedding_model,
            "device": self.embedding_device,
            "normalized": self.embedding_normalize,
            "batch_size": self.embedding_batch_size,
        }
        metadata.update(self._provider_metadata)
        return metadata

    @staticmethod
    def _safe_emit(callback: Callable[..., None], **kwargs: Any) -> None:
        try:
            callback(**kwargs)
        except Exception:
            logger.exception("Embedding pipeline event emit hiba")


__all__ = ["EmbeddingPipelineService"]
