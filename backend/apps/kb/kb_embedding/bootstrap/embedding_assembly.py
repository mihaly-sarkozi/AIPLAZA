from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_embedding.adapters.DummyEmbeddingAdapter import DummyEmbeddingAdapter
from apps.kb.kb_embedding.adapters.LocalEmbeddingAdapter import LocalEmbeddingAdapter
from apps.kb.kb_embedding.bootstrap.embedding_provider_guard import validate_embedding_provider_runtime
from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository
from apps.kb.kb_embedding.service.BuildEmbeddingInputService import BuildEmbeddingInputService
from apps.kb.kb_embedding.service.EmbeddingPipelineService import EmbeddingPipelineService
from apps.kb.kb_embedding.service.GenerateEmbeddingService import GenerateEmbeddingService
from apps.kb.kb_embedding.service.StartEmbeddingService import StartEmbeddingService
from apps.kb.kb_embedding.service.StoreEmbeddingService import StoreEmbeddingService
from apps.kb.kb_embedding.service.ValidateEmbeddingService import ValidateEmbeddingService
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder
from core.kernel.config.config_loader import settings


@dataclass(frozen=True)
class EmbeddingServices:
    job_repository: EmbeddingJobRepository
    embedding_repository: KnowledgeEmbeddingRepository
    start_service: StartEmbeddingService
    pipeline: EmbeddingPipelineService


def _build_embedding_provider(provider_name: str, dimension: int, batch_size: int):
    name = (provider_name or "").strip().lower()
    if name == "openai":
        from apps.kb.kb_embedding.adapters.OpenAIEmbeddingAdapter import OpenAIEmbeddingAdapter

        return OpenAIEmbeddingAdapter(), False, {}
    if name == "dummy":
        return DummyEmbeddingAdapter(dimension=dimension), False, {}
    if name == "local":
        cache_dir = str(getattr(settings, "embedding_model_cache_dir", "") or "").strip() or None
        adapter = LocalEmbeddingAdapter(
            default_model=str(settings.embedding_model or "BAAI/bge-m3"),
            expected_dimension=dimension,
            device=str(getattr(settings, "embedding_device", "cpu") or "cpu"),
            batch_size=batch_size,
            normalize_embeddings=bool(getattr(settings, "embedding_normalize", True)),
            cache_folder=cache_dir,
        )
        return adapter, True, adapter.metadata
    raise ValueError(f"Ismeretlen embedding provider: {provider_name}")


def build_embedding_services(
    *,
    session_factory,
    chunk_reader,
    discovery_job_reader,
    bundle_reader,
    flow_recorder=None,
) -> EmbeddingServices:
    validate_embedding_provider_runtime(settings)

    job_repository = EmbeddingJobRepository(session_factory)
    embedding_repository = KnowledgeEmbeddingRepository(session_factory)
    embedding_model = str(settings.embedding_model or "BAAI/bge-m3")
    embedding_provider = str(settings.embedding_provider or "local").strip().lower()
    embedding_dimension = int(settings.embedding_vector_size or 1024)
    embedding_batch_size = int(settings.embedding_batch_size or 16)
    recorder = flow_recorder or NoOpProcessingFlowRecorder()

    provider, is_local, provider_metadata = _build_embedding_provider(
        embedding_provider,
        embedding_dimension,
        embedding_batch_size,
    )

    build_input = BuildEmbeddingInputService()
    generate = GenerateEmbeddingService(
        provider,
        expected_dimension=embedding_dimension,
        batch_size=embedding_batch_size,
        local_provider=is_local,
    )
    store = StoreEmbeddingService(embedding_repository)
    validate = ValidateEmbeddingService(embedding_repository)
    pipeline = EmbeddingPipelineService(
        job_repository,
        embedding_repository,
        bundle_reader,
        build_input,
        generate,
        store,
        validate,
        embedding_model=embedding_model,
        embedding_provider=embedding_provider,
        embedding_dimension=embedding_dimension,
        embedding_batch_size=embedding_batch_size,
        embedding_device=str(getattr(settings, "embedding_device", "cpu") or "cpu"),
        embedding_normalize=bool(getattr(settings, "embedding_normalize", True)),
        provider_metadata=provider_metadata,
        flow_recorder=recorder,
    )
    start_service = StartEmbeddingService(
        job_repository,
        chunk_reader,
        discovery_job_reader,
        pipeline,
    )
    return EmbeddingServices(
        job_repository=job_repository,
        embedding_repository=embedding_repository,
        start_service=start_service,
        pipeline=pipeline,
    )


__all__ = ["EmbeddingServices", "build_embedding_services"]
