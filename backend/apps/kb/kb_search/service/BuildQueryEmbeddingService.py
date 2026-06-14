from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import desc, select

from apps.kb.kb_embedding.orm.EmbeddingJob import EmbeddingJob
from apps.kb.kb_search.adapters.QueryEmbeddingProviderAdapter import QueryEmbeddingProviderAdapter
from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode
from core.kernel.config.config_loader import settings

logger = logging.getLogger(__name__)


class BuildQueryEmbeddingService:
    def __init__(
        self,
        *,
        session_factory,
        query_embedding_adapter: QueryEmbeddingProviderAdapter,
    ) -> None:
        self._session_factory = session_factory
        self._adapter = query_embedding_adapter

    def build(
        self,
        *,
        question: str,
        knowledge_base_id: str,
    ) -> dict[str, Any]:
        model, dimension = self._resolve_model(knowledge_base_id)
        try:
            vector, resolved_model, resolved_dim = self._adapter.embed_query(
                question,
                model=model,
                expected_dimension=dimension,
            )
        except Exception as exc:
            code = getattr(exc, "code", None) or SearchErrorCode.QUERY_EMBEDDING_FAILED.value
            logger.warning("Query embedding failed: %s", exc)
            raise RuntimeError(str(code)) from exc
        return {
            "query_vector": vector,
            "embedding_model": resolved_model,
            "embedding_dimension": resolved_dim,
        }

    def _resolve_model(self, knowledge_base_id: str) -> tuple[str, int]:
        with self._session_factory() as session:
            row = (
                session.execute(
                    select(EmbeddingJob)
                    .where(
                        EmbeddingJob.knowledge_base_id == knowledge_base_id,
                        EmbeddingJob.status.in_(("COMPLETED", "PARTIAL")),
                    )
                    .order_by(desc(EmbeddingJob.finished_at), desc(EmbeddingJob.created_at))
                    .limit(1)
                )
                .scalars()
                .first()
            )
        if row is not None and row.embedding_model:
            return str(row.embedding_model), int(row.embedding_dimension or settings.embedding_vector_size or 1024)
        return (
            str(settings.embedding_model or "BAAI/bge-m3"),
            int(settings.embedding_vector_size or 1024),
        )


__all__ = ["BuildQueryEmbeddingService"]
