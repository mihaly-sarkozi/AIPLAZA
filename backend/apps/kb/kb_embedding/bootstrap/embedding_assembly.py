from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_embedding.adapters.DummyEmbeddingAdapter import DummyEmbeddingAdapter
from apps.kb.kb_embedding.adapters.LocalEmbeddingAdapter import LocalEmbeddingAdapter
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


def _build_embedding_provider(provider_name: str, dimension: int):
    name = (provider_name or "").strip().lower()
    if name == "openai":
        from apps.kb.kb_embedding.adapters.OpenAIEmbeddingAdapter import OpenAIEmbeddingAdapter

        return OpenAIEmbeddingAdapter()
    if name == "local":
        return LocalEmbeddingAdapter(dimension=dimension)
    if name == "dummy":
        return DummyEmbeddingAdapter(dimension=dimension)
    return LocalEmbeddingAdapter(dimension=dimension)


def build_embedding_services(
    *,
    session_factory,
    chunk_reader,
    discovery_job_reader,
    bundle_reader,
    flow_recorder=None,
) -> EmbeddingServices:
    job_repository = EmbeddingJobRepository(session_factory)
    embedding_repository = KnowledgeEmbeddingRepository(session_factory)
    embedding_model = str(settings.embedding_model or "BAAI/bge-m3")
    embedding_provider = str(settings.embedding_provider or "local")
    embedding_dimension = int(settings.embedding_vector_size or 1024)
    provider = _build_embedding_provider(embedding_provider, embedding_dimension)

    build_input = BuildEmbeddingInputService()
    generate = GenerateEmbeddingService(provider, expected_dimension=embedding_dimension)
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
        flow_recorder=flow_recorder or NoOpProcessingFlowRecorder(),
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
