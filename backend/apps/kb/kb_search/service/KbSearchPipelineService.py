from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from core.kernel.interface.observability import increment_metric, log_structured_event

from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode
from apps.kb.kb_search.enums.SearchMode import SearchMode
from apps.kb.kb_search.enums.SearchStatus import SearchStatus
from apps.kb.kb_search.errors.SearchNotReadyError import SearchNotReadyError
from apps.kb.kb_search.repository.SearchQueryRunRepository import SearchQueryRunRepository
from apps.kb.kb_search.service.BuildCitationService import BuildCitationService
from apps.kb.kb_search.service.BuildQueryEmbeddingService import BuildQueryEmbeddingService
from apps.kb.kb_search.service.BuildSearchContextService import BuildSearchContextService
from apps.kb.kb_search.service.BuildSearchQueryService import BuildSearchQueryService
from apps.kb.kb_search.service.HybridRankService import HybridRankService
from apps.kb.kb_search.service.PostgresHydrationService import PostgresHydrationService
from apps.kb.kb_search.service.QdrantVectorSearchService import QdrantVectorSearchService
from apps.kb.kb_search.service.SearchReadinessService import SearchReadinessService
from apps.kb.kb_search.service.StoreSearchRunService import StoreSearchRunService

logger = logging.getLogger(__name__)


class KbSearchPipelineService:
    def __init__(
        self,
        *,
        run_repository: SearchQueryRunRepository,
        readiness_service: SearchReadinessService,
        build_query_service: BuildSearchQueryService,
        build_embedding_service: BuildQueryEmbeddingService,
        vector_search_service: QdrantVectorSearchService,
        hybrid_rank_service: HybridRankService,
        hydration_service: PostgresHydrationService,
        build_context_service: BuildSearchContextService,
        build_citation_service: BuildCitationService,
        store_run_service: StoreSearchRunService,
        knowledge_base_reader,
        default_top_k: int = 10,
    ) -> None:
        self._runs = run_repository
        self._readiness = readiness_service
        self._build_query = build_query_service
        self._build_embedding = build_embedding_service
        self._vector_search = vector_search_service
        self._hybrid_rank = hybrid_rank_service
        self._hydration = hydration_service
        self._build_context = build_context_service
        self._build_citation = build_citation_service
        self._store = store_run_service
        self._kb_reader = knowledge_base_reader
        self._default_top_k = default_top_k

    def execute(
        self,
        *,
        question: str,
        knowledge_base_id: str,
        kb_uuid: str,
        tenant_slug: str | None = None,
        user_id: int | None = None,
        channel_id: str | None = None,
        conversation_id: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        top_k: int | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        started = perf_counter()
        log_structured_event(
            "apps.kb.kb_search",
            "KB_SEARCH_STARTED",
            level=logging.INFO,
            knowledge_base_id=knowledge_base_id,
        )
        run = self._runs.new_run(
            tenant_slug=tenant_slug,
            user_id=user_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            knowledge_base_id=knowledge_base_id,
            kb_uuid=kb_uuid,
            question=question,
            normalized_question=question,
            search_mode=SearchMode.HYBRID.value,
            top_k=int(top_k or self._default_top_k),
            ranking_config={
                "vector_score_weight": 0.75,
                "knowledge_score_weight": 0.25,
            },
        )
        run.status = SearchStatus.RUNNING.value
        self._runs.create(run)

        try:
            readiness = self._readiness.check(knowledge_base_id=knowledge_base_id, tenant_slug=tenant_slug)
        except SearchNotReadyError as exc:
            run.status = SearchStatus.BLOCKED_NOT_READY.value
            run.error_code = SearchErrorCode.KB_NOT_READY.value
            run.error_message = exc.message
            run.duration_ms = int((perf_counter() - started) * 1000)
            self._runs.update(run)
            increment_metric("kb.search.blocked_not_ready", 1.0)
            log_structured_event(
                "apps.kb.kb_search",
                "SEARCH_KB_NOT_READY",
                level=logging.WARNING,
                knowledge_base_id=knowledge_base_id,
            )
            return self._blocked_packet(run, readiness={"ready_for_search": False, "blocked_reasons": list(exc.blocked_reasons)})

        query_profile = self._build_query.build(
            question=question,
            conversation_history=conversation_history,
            knowledge_base_id=knowledge_base_id,
            channel_id=channel_id,
            user_id=user_id,
        )
        run.normalized_question = query_profile["normalized_question"]
        run.rewritten_question = query_profile["rewritten_question"]
        run.language_code = query_profile.get("language_code")
        run.filters_json = dict(query_profile.get("filters") or {})

        try:
            embedding = self._build_embedding.build(
                question=query_profile["rewritten_question"],
                knowledge_base_id=knowledge_base_id,
            )
        except RuntimeError:
            run.status = SearchStatus.FAILED.value
            run.error_code = SearchErrorCode.QUERY_EMBEDDING_FAILED.value
            run.duration_ms = int((perf_counter() - started) * 1000)
            self._runs.update(run)
            increment_metric("kb.search.embedding_failed", 1.0)
            raise

        run.query_embedding_model = embedding["embedding_model"]
        run.query_embedding_dimension = embedding["embedding_dimension"]

        try:
            hits = self._vector_search.search(
                knowledge_base_id=knowledge_base_id,
                query_vector=embedding["query_vector"],
                top_k=run.top_k,
                filters=run.filters_json,
            )
        except Exception:
            run.status = SearchStatus.FAILED.value
            run.error_code = SearchErrorCode.QDRANT_FAILED.value
            run.duration_ms = int((perf_counter() - started) * 1000)
            self._runs.update(run)
            increment_metric("kb.search.qdrant_failed", 1.0)
            raise

        ranked = self._hybrid_rank.rank(hits)
        hydrated = self._hydration.hydrate(ranked)
        context_blocks, prompt_context = self._build_context.build(hydrated)
        citations, citation_ids = self._build_citation.build(
            context_blocks,
            kb_uuid=kb_uuid,
            query_run_id=run.id,
        )

        collection = self._kb_reader.get_qdrant_collection_name(knowledge_base_id)
        if not context_blocks:
            run.status = SearchStatus.NO_RESULTS.value
            run.error_code = SearchErrorCode.NO_RESULTS.value
            increment_metric("kb.search.no_results", 1.0)
            log_structured_event(
                "apps.kb.kb_search",
                "KB_SEARCH_NO_RESULTS",
                level=logging.INFO,
                query_run_id=run.id,
            )
        else:
            run.status = SearchStatus.COMPLETED.value
            log_structured_event(
                "apps.kb.kb_search",
                "KB_SEARCH_COMPLETED",
                level=logging.INFO,
                query_run_id=run.id,
            )

        run.duration_ms = int((perf_counter() - started) * 1000)
        self._store.store(
            run=run,
            ranked_hits=hydrated,
            context_blocks=context_blocks,
            citations=citations,
            collection_name=collection,
        )

        matched_chunks = [
            {
                "chunk_id": block.get("chunk_id"),
                "training_item_id": block.get("training_item_id"),
                "rank": block.get("rank"),
                "qdrant_score": block.get("qdrant_score"),
                "hybrid_score": block.get("hybrid_score"),
                "overall_score": block.get("overall_score"),
                "document_title": block.get("document_title"),
                "section_title": block.get("section_title"),
                "page_numbers": block.get("page_numbers"),
                "snippet": block.get("snippet"),
                "citation_id": block.get("citation_id"),
            }
            for block in context_blocks
        ]

        sources = [
            {
                "citation_id": c.get("citation_id"),
                "source_id": c.get("source_id"),
                "document_title": c.get("document_title"),
                "page_numbers": c.get("page_numbers"),
                "section_title": c.get("section_title"),
                "snippet": c.get("snippet"),
                "kb_uuid": kb_uuid,
                "download_url": c.get("download_url") or c.get("download_ref"),
                "download_url_template": c.get("download_url_template"),
            }
            for c in citations
        ]

        packet = {
            "query_run_id": run.id,
            "answer_mode": "ANSWERED" if context_blocks else "NO_ANSWER",
            "context_blocks": context_blocks,
            "matched_chunks": matched_chunks,
            "evidence_summary": citations,
            "cited_source_ids": [c.get("source_id") for c in citations if c.get("source_id")],
            "sources": sources,
            "citations": citation_ids,
            "query_profile": query_profile,
            "scoring_summary": {
                "hit_count": len(hits),
                "ranked_count": len(ranked),
                "context_block_count": len(context_blocks),
                "latency_ms": {"search_total": float(run.duration_ms or 0)},
            },
            "prompt_context": prompt_context,
            "encoded_prompt_context": prompt_context,
            "readiness": readiness,
            "kb_uuid": kb_uuid,
            "corpus_uuid": kb_uuid,
        }
        if debug:
            packet["debug"] = {
                "qdrant_results": ranked[:20],
                "hybrid_ranking": [
                    {
                        "rank": row.get("rank"),
                        "chunk_id": (row.get("payload") or {}).get("chunk_id"),
                        "qdrant_score": row.get("score"),
                        "hybrid_score": row.get("hybrid_score"),
                    }
                    for row in ranked[:20]
                ],
                "query_run": {
                    "status": run.status,
                    "normalized_question": run.normalized_question,
                    "rewritten_question": run.rewritten_question,
                },
            }
        return packet

    @staticmethod
    def _blocked_packet(run, *, readiness: dict[str, Any]) -> dict[str, Any]:
        return {
            "query_run_id": run.id,
            "answer_mode": "BLOCKED_NOT_READY",
            "context_blocks": [],
            "matched_chunks": [],
            "evidence_summary": [],
            "cited_source_ids": [],
            "sources": [],
            "citations": [],
            "query_profile": {},
            "scoring_summary": {},
            "prompt_context": "",
            "encoded_prompt_context": "",
            "readiness": readiness,
            "blocked_message": "A kiválasztott tudástár még nem kereshető. Az indexelés vagy ellenőrzés nem fejeződött be.",
        }


__all__ = ["KbSearchPipelineService"]
