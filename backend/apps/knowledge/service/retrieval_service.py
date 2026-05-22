# backend/apps/knowledge/service/retrieval_service.py
# Feladat: Knowledge retrieval es chat-context response osszeallitasi boundary.
# A keresesi futtatast komponens moge rejti, a chat adapternek szukseges source
# metaadat/citation payloadot pedig a facade helyett itt allitja elo.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from apps.knowledge.domain.context_profile import ContextProfile
from apps.knowledge.domain.query_run import QueryRun
from apps.knowledge.domain.retrieval_profile import RetrievalProfile
from apps.knowledge.domain.source import Source
from apps.knowledge.service.ports import CorpusStorePort, DocumentStorePort, SourceStorePort


class RetrievalService:
    def __init__(
        self,
        *,
        source_store: SourceStorePort,
        document_store: DocumentStorePort,
        corpus_store: CorpusStorePort,
        retrieve_query: Callable[..., Any],
        source_display_type: Callable[[Source], str],
        source_created_by_label: Callable[[Source], str],
    ) -> None:
        self._source_store = source_store
        self._document_store = document_store
        self._corpus_store = corpus_store
        self._retrieve_query = retrieve_query
        self._source_display_type = source_display_type
        self._source_created_by_label = source_created_by_label

    def _require_tenant_scoped_corpus(self, *, tenant: str, corpus_uuid: str):
        effective_tenant = str(tenant or "").strip()
        if not effective_tenant:
            raise PermissionError("Tenant scope is required for knowledge retrieval")
        corpus = self._corpus_store.get_by_uuid(corpus_uuid)
        if corpus is None:
            raise PermissionError("Knowledge base is not in tenant scope")
        if str(getattr(corpus, "tenant", "") or "").strip() != effective_tenant:
            raise PermissionError("Knowledge base is not in tenant scope")
        return corpus

    async def retrieve(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        compare_mode: bool = False,
    ) -> QueryRun:
        self._require_tenant_scoped_corpus(tenant=tenant, corpus_uuid=corpus_uuid)
        return await self._retrieve_query(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=compare_mode,
        )

    async def build_chat_context(
        self,
        *,
        tenant: str | None = None,
        corpus_uuid: str | None = None,
        query: str | None = None,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        question: str | None = None,
        kb_uuid: str | None = None,
        current_user_id: int | None = None,
        current_user_role: str | None = None,
        parsed_query: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        effective_query = str(query or question or "").strip()
        effective_corpus_uuid = str(corpus_uuid or kb_uuid or "").strip()
        if not effective_query:
            raise ValueError("Query is required for chat context build")
        if not effective_corpus_uuid:
            raise ValueError("Corpus UUID is required for chat context build")
        corpus = self._require_tenant_scoped_corpus(
            tenant=tenant or "",
            corpus_uuid=effective_corpus_uuid,
        )
        run = await self.retrieve(
            tenant=tenant or "",
            corpus_uuid=effective_corpus_uuid,
            query=effective_query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=len(build_ids or []) > 1,
        )
        source_metadata_by_id = self._collect_source_metadata(run)
        source_chunks = self._build_source_chunks(
            run=run,
            corpus_uuid=effective_corpus_uuid,
            source_metadata_by_id=source_metadata_by_id,
        )
        return {
            "query_run_id": run.id,
            "kb_uuid": effective_corpus_uuid,
            "corpus_uuid": effective_corpus_uuid,
            "context_text": run.context_text,
            "citations": [
                {
                    "source_id": item.source_id,
                    "build_id": item.build_id,
                    "snippet": item.snippet,
                    "title": item.title,
                    "score": item.score,
                    "chunk_id": item.chunk_id,
                }
                for item in run.citations
            ],
            "build_ids": run.build_ids,
            "retrieval_profile_key": run.retrieval_profile_key,
            "context_profile_key": run.context_profile_key,
            "query_profile": run.metadata.get("query_profile"),
            "query_detected_entities": run.metadata.get("query_detected_entities") or [],
            "query_intent": run.metadata.get("query_intent"),
            "query_filters": run.metadata.get("query_filters") or {},
            "query_resolution_confidence": run.metadata.get("query_resolution_confidence") or 0.0,
            "query_aware_retrieval": run.metadata.get("query_aware_retrieval") or {},
            "matched_chunks": run.metadata.get("matched_chunks") or [],
            "matched_claims": run.metadata.get("matched_claims") or [],
            "matched_semantic_blocks": run.metadata.get("matched_semantic_blocks") or [],
            "filtered_out_reason": run.metadata.get("filtered_out_reason") or [],
            "retrieval_confidence": run.metadata.get("retrieval_confidence") or 0.0,
            "query_retrieval_match_count": run.metadata.get("query_retrieval_match_count") or 0,
            "query_retrieval_filtered_count": run.metadata.get("query_retrieval_filtered_count") or 0,
            "conflict_marker_included": bool(run.metadata.get("conflict_marker_included")),
            "temporal_context_used": bool(run.metadata.get("temporal_context_used")),
            "answer_text": run.metadata.get("answer_text") or "",
            "answer_mode": run.metadata.get("answer_mode") or "no_answer",
            "cited_claim_ids": run.metadata.get("cited_claim_ids") or [],
            "cited_evidence_ids": run.metadata.get("cited_evidence_ids") or [],
            "cited_sentence_ids": run.metadata.get("cited_sentence_ids") or [],
            "cited_source_ids": run.metadata.get("cited_source_ids") or run.metadata.get("source_ids") or [],
            "source_ids": run.metadata.get("source_ids") or [],
            "evidence_summary": run.metadata.get("evidence_summary") or [],
            "explanation": run.metadata.get("explanation") or {},
            "lineage": run.metadata.get("lineage") or {},
            "synthesis_confidence": run.metadata.get("synthesis_confidence") or 0.0,
            "query_debug": run.metadata.get("query_debug") or {},
            "no_ready_index_build": bool(run.metadata.get("no_ready_index_build")),
            "top_assertions": [],
            "evidence_sentences": [],
            "source_chunks": source_chunks,
            "related_entities": [],
            "scoring_summary": {
                "latency_ms": {"retrieve": run.latency_ms},
                "result_count": run.result_count,
            },
            "query_focus": parsed_query or {},
            "debug_enabled": debug,
            "current_user_id": current_user_id,
            "current_user_role": current_user_role,
            "pii_depersonalization_enabled": bool(getattr(corpus, "pii_depersonalization_enabled", True)),
            "personal_data_sensitivity": str(getattr(corpus, "personal_data_sensitivity", "medium") or "medium"),
        }

    async def answer_support(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        packet = await self.build_chat_context(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
        )
        return {
            "question": query,
            "context_text": packet["context_text"],
            "citations": packet["citations"],
        }

    def _collect_source_metadata(self, run: QueryRun) -> dict[str, Source]:
        source_metadata_by_id: dict[str, Source] = {}
        for source_id in run.metadata.get("cited_source_ids") or run.metadata.get("source_ids") or []:
            source = self._source_store.get(str(source_id))
            if source is not None:
                source_metadata_by_id[source.id] = source
        for block in run.metadata.get("context_blocks") or run.metadata.get("matched_semantic_blocks") or []:
            if not isinstance(block, dict):
                continue
            source_id = str(block.get("source_id") or "").strip()
            if not source_id or source_id in source_metadata_by_id:
                continue
            source = self._source_store.get(source_id)
            if source is not None:
                source_metadata_by_id[source.id] = source
        for citation in run.citations:
            if citation.source_id and citation.source_id not in source_metadata_by_id:
                source = self._source_store.get(citation.source_id)
                if source is not None:
                    source_metadata_by_id[source.id] = source
        return source_metadata_by_id

    def _build_source_chunks(
        self,
        *,
        run: QueryRun,
        corpus_uuid: str,
        source_metadata_by_id: dict[str, Source],
    ) -> list[dict[str, Any]]:
        source_chunks = [
            {
                "id": citation.chunk_id or f"source-{index}",
                "kb_uuid": corpus_uuid,
                "source_point_id": citation.source_id or citation.chunk_id or f"source-{index}",
                "source_id": citation.source_id or "",
                "source_document_title": citation.title or "",
                "text": citation.snippet,
                "score": citation.score,
                "build_id": citation.build_id,
                "source_type": getattr(source_metadata_by_id.get(citation.source_id), "source_type", ""),
                "file_ref": getattr(source_metadata_by_id.get(citation.source_id), "file_ref", None),
                "display_type": (
                    self._source_display_type(source_metadata_by_id[citation.source_id])
                    if citation.source_id in source_metadata_by_id
                    else ""
                ),
                "created_by": getattr(source_metadata_by_id.get(citation.source_id), "created_by", None),
                "created_by_label": (
                    self._source_created_by_label(source_metadata_by_id[citation.source_id])
                    if citation.source_id in source_metadata_by_id
                    else ""
                ),
                "created_at": (
                    source_metadata_by_id[citation.source_id].created_at.isoformat()
                    if citation.source_id in source_metadata_by_id and source_metadata_by_id[citation.source_id].created_at
                    else None
                ),
            }
            for index, citation in enumerate(run.citations, start=1)
        ]
        existing_source_chunk_ids = {
            str(item.get("source_id") or item.get("source_point_id") or "").strip()
            for item in source_chunks
        }
        for source_id, source in source_metadata_by_id.items():
            if source_id in existing_source_chunk_ids:
                continue
            document = self._document_store.get_for_source(source_id)
            source_chunks.append(
                {
                    "id": f"source-{source_id}",
                    "kb_uuid": corpus_uuid,
                    "source_point_id": source_id,
                    "source_id": source_id,
                    "source_document_title": source.title,
                    "text": (document.text_content if document is not None else str(source.raw_content or ""))[:400],
                    "score": 0.0,
                    "build_id": "",
                    "source_type": source.source_type,
                    "file_ref": source.file_ref,
                    "display_type": self._source_display_type(source),
                    "created_by": source.created_by,
                    "created_by_label": self._source_created_by_label(source),
                    "created_at": source.created_at.isoformat() if source.created_at else None,
                }
            )
        return source_chunks


__all__ = ["RetrievalService"]
