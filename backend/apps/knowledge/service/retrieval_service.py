# backend/apps/knowledge/service/retrieval_service.py
# Feladat: Knowledge retrieval es chat-context response osszeallitasi boundary.
# A keresesi futtatast komponens moge rejti, a chat adapternek szukseges source
# metaadat/citation payloadot pedig a facade helyett itt allitja elo.

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import time
from typing import Any

from apps.knowledge.domain.context_profile import DEFAULT_CONTEXT_PROFILE, ContextProfile
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.query_profile import query_profile_to_json_dict
from apps.knowledge.domain.query_run import Citation, QueryRun
from apps.knowledge.domain.retrieval_profile import DEFAULT_RETRIEVAL_PROFILE, RetrievalProfile
from apps.knowledge.domain.source import Source
from apps.knowledge.service.answer_verifier import verify_answer
from apps.knowledge.service.explanation_builder_v0 import ExplanationBuilderV0
from apps.knowledge.service.facade_helpers import json_safe as _json_safe
from apps.knowledge.service.lineage_builder_v0 import LineageBuilderV0
from apps.knowledge.service.ports import CorpusStorePort, DocumentStorePort, SourceStorePort
from apps.knowledge.service.query_aware_retrieval_v0 import QueryAwareRetrievalV0
from apps.knowledge.service.query_resolver_v0 import QueryResolverV0
from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0
from apps.knowledge.service.synthesis_engine_v0 import SynthesisEngineV0
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    log_structured_event,
    observe_metric as observe_platform_metric,
)

logger = logging.getLogger(__name__)

_RETRIEVAL_TIMEOUT_SECONDS = 3.0
_RETRIEVAL_RETRY_ATTEMPTS = 2
_RETRIEVAL_RETRY_BACKOFF_SECONDS = 0.05


class RetrievalService:
    def __init__(
        self,
        *,
        source_store: SourceStorePort,
        document_store: DocumentStorePort,
        corpus_store: CorpusStorePort,
        source_display_type: Callable[[Source], str],
        source_created_by_label: Callable[[Source], str],
        retrieve_query: Callable[..., Any] | None = None,
        dependency_host: Any | None = None,
    ) -> None:
        self._source_store = source_store
        self._document_store = document_store
        self._corpus_store = corpus_store
        self._retrieve_query = retrieve_query
        self._source_display_type = source_display_type
        self._source_created_by_label = source_created_by_label
        self._dependency_host = dependency_host

    def __getattr__(self, name: str) -> Any:
        if self._dependency_host is not None:
            return getattr(self._dependency_host, name)
        raise AttributeError(name)

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
        if self._dependency_host is not None:
            return await self.retrieve_query_run(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                query=query,
                build_ids=build_ids,
                retrieval_profile=retrieval_profile,
                context_profile=context_profile,
                compare_mode=compare_mode,
            )
        if self._retrieve_query is None:
            raise RuntimeError("Retrieval query runner is not configured")
        return await self._retrieve_query(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=compare_mode,
        )

    async def retrieve_hits_with_resilience(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        last_error: BaseException | None = None
        for attempt in range(1, _RETRIEVAL_RETRY_ATTEMPTS + 1):
            started = time.perf_counter()
            try:
                hits = await asyncio.wait_for(
                    self._retrieval_engine.retrieve(
                        query=query,
                        builds=builds,
                        retrieval_profile=retrieval_profile,
                        query_profile=query_profile,
                    ),
                    timeout=_RETRIEVAL_TIMEOUT_SECONDS,
                )
                self._metrics_store.record_timing("query_retrieval_duration_ms", (time.perf_counter() - started) * 1000.0)
                observe_platform_metric("knowledge.query.retrieval.duration_ms", (time.perf_counter() - started) * 1000.0, unit="ms")
                return hits
            except (TimeoutError, asyncio.TimeoutError) as exc:
                last_error = exc
                self._metrics_store.increment("query_retrieval_timeout_count", 1)
                increment_platform_metric("knowledge.query.retrieval.timeout.count", 1.0)
                log_structured_event(
                    "apps.knowledge",
                    "knowledge.query.retrieval_timeout",
                    level=logging.WARNING,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    retry_count=attempt,
                    timeout_sec=_RETRIEVAL_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                last_error = exc
                self._metrics_store.increment("query_retrieval_error_count", 1)
                increment_platform_metric("knowledge.query.retrieval.error.count", 1.0)
                log_structured_event(
                    "apps.knowledge",
                    "knowledge.query.retrieval_error",
                    level=logging.WARNING,
                    tenant=tenant,
                    corpus_uuid=corpus_uuid,
                    retry_count=attempt,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
            if attempt < _RETRIEVAL_RETRY_ATTEMPTS:
                await asyncio.sleep(_RETRIEVAL_RETRY_BACKOFF_SECONDS * attempt)
        self._metrics_store.increment("query_retrieval_fallback_count", 1)
        increment_platform_metric("knowledge.query.retrieval.fallback.count", 1.0)
        if last_error is not None:
            log_structured_event(
                "apps.knowledge",
                "knowledge.query.retrieval_profile_fallback",
                level=logging.WARNING,
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                error_type=type(last_error).__name__,
                error_message=str(last_error),
            )
        return []

    async def retrieve_query_run(
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
        started = time.perf_counter()
        retrieval = retrieval_profile or DEFAULT_RETRIEVAL_PROFILE
        context = context_profile or DEFAULT_CONTEXT_PROFILE
        query_profile = query_profile_to_json_dict(QueryResolverV0().resolve(query))
        builds = self._resolve_builds(corpus_uuid=corpus_uuid, build_ids=build_ids)
        no_ready_index_build = not builds
        hits = []
        if builds:
            hits = await self.retrieve_hits_with_resilience(
                tenant=tenant,
                corpus_uuid=corpus_uuid,
                query=query,
                builds=builds,
                retrieval_profile=retrieval,
                query_profile=query_profile,
            )
            if retrieval.score_threshold is not None:
                hits = [
                    item for item in hits if float(item.get("fusion_score") or item.get("score") or 0.0) >= retrieval.score_threshold
                ]
        query_global_profiles = self._load_existing_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        query_global_profiles, feedback_events = self._knowledge_feedback_service.apply_feedback_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=query_global_profiles,
        )
        query_global_profiles, source_withdrawal_events = self._knowledge_feedback_service.apply_source_withdrawals_to_global_profiles(
            corpus_uuid=corpus_uuid,
            global_profiles=query_global_profiles,
        )
        if feedback_events or source_withdrawal_events:
            query_retrieval_chunks = RetrievalChunkBuilderV0().build_many(query_global_profiles, [])
        else:
            query_retrieval_chunks = self._load_existing_retrieval_chunks(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=None,
            )
            if not query_retrieval_chunks and query_global_profiles:
                query_retrieval_chunks = RetrievalChunkBuilderV0().build_many(query_global_profiles, [])
        query_retrieval_chunks = self._order_chunks_by_vector_hits(query_retrieval_chunks, hits)
        query_aware_result = QueryAwareRetrievalV0().match(
            query_profile=query_profile,
            retrieval_chunks=query_retrieval_chunks,
            global_profiles=query_global_profiles,
        )
        matched_chunks = list(query_aware_result.get("matched_chunks") or [])
        matched_claims = self._lineage_service.enrich_matched_claims_for_explanation(list(query_aware_result.get("matched_claims") or []))
        query_aware_result["matched_claims"] = matched_claims
        semantic_blocks = self._load_existing_semantic_blocks(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=None,
        )
        vector_matched_semantic_blocks = self._semantic_blocks_from_vector_hits(hits)
        lexical_matched_semantic_blocks = self._select_semantic_blocks_for_query(
            semantic_blocks=semantic_blocks,
            matched_claims=matched_claims,
            matched_chunks=matched_chunks,
            query_profile=query_profile,
            query=query,
        )
        matched_semantic_blocks: list[dict[str, Any]] = []
        seen_block_ids: set[str] = set()
        for block in [*vector_matched_semantic_blocks, *lexical_matched_semantic_blocks]:
            block_id = str(block.get("id") or "").strip()
            if not block_id or block_id in seen_block_ids:
                continue
            seen_block_ids.add(block_id)
            matched_semantic_blocks.append(block)
        matched_semantic_blocks = self._filter_relevant_semantic_blocks(
            matched_semantic_blocks,
            max_blocks=4,
        )
        if not matched_chunks and matched_semantic_blocks:
            fallback_chunks: list[dict[str, Any]] = []
            fallback_claims: list[dict[str, Any]] = []
            for block in matched_semantic_blocks:
                source_id = str(block.get("source_id") or "").strip()
                sentence_ids = [str(item).strip() for item in (block.get("sentence_ids") or []) if str(item).strip()]
                claim_ids = [str(item).strip() for item in (block.get("claim_ids") or []) if str(item).strip()]
                block_id = str(block.get("id") or block.get("block_id") or "").strip()
                entity_name = str(block.get("primary_subject") or "").strip()
                claim_text = str(block.get("summary") or block.get("text") or "").strip()
                if not source_id or not claim_text:
                    continue
                if not sentence_ids:
                    sentence_ids = [f"{block_id or source_id}-sentence-1"]
                if not claim_ids:
                    claim_ids = [f"{block_id or source_id}-claim-1"]
                chunk_confidence = float(block.get("match_score") or 0.0)
                chunk_confidence = max(0.45, min(round(chunk_confidence / 2.0, 4), 0.95))
                fallback_chunks.append(
                    {
                        "profile_id": str(block.get("profile_id") or ""),
                        "entity_name": entity_name,
                        "retrieval_chunk_text": claim_text,
                        "conflict_marker": bool(block.get("conflict_count")),
                        "temporal_context_used": False,
                        "matched_claim_ids": claim_ids,
                        "evidence_ids": sentence_ids,
                        "source_ids": [source_id],
                        "retrieval_confidence": chunk_confidence,
                    }
                )
                for claim_id in claim_ids:
                    fallback_claims.append(
                        {
                            "profile_id": str(block.get("profile_id") or ""),
                            "entity_name": entity_name,
                            "claim_id": claim_id,
                            "claim_text": claim_text,
                            "raw_claim_text": claim_text,
                            "canonical_claim_text": claim_text,
                            "display_claim_text": claim_text,
                            "language": str(block.get("language") or ""),
                            "predicate": "",
                            "object": "",
                            "fact_bucket": "descriptors",
                            "claim_group": "descriptor",
                            "claim_semantic_type": "attribute",
                            "state": "",
                            "time_filter": "",
                            "time_values": list(block.get("time_values") or []),
                            "sentence_ids": sentence_ids,
                            "source_ids": [source_id],
                            "conflict_marker": bool(block.get("conflict_count")),
                        }
                    )
            if fallback_chunks:
                matched_chunks = fallback_chunks
                matched_claims = self._lineage_service.enrich_matched_claims_for_explanation(fallback_claims)
                query_aware_result["matched_chunks"] = matched_chunks
                query_aware_result["matched_claims"] = matched_claims
                query_aware_result["retrieval_confidence"] = round(
                    sum(float(item.get("retrieval_confidence") or 0.0) for item in matched_chunks) / len(matched_chunks),
                    4,
                )
                query_aware_result["query_retrieval_match_count"] = len(matched_chunks)
        synthesis_result = SynthesisEngineV0().synthesize(
            query_profile=query_profile,
            matched_chunks=matched_chunks,
            matched_claims=matched_claims,
        )
        answer_mode = str(synthesis_result.get("answer_mode") or "no_answer")
        conflict_marker_included = (
            bool(query_aware_result.get("conflict_marker_included"))
            or answer_mode == "conflict"
            or any(bool(item.get("conflict_marker")) for item in matched_claims)
        )
        evidence_summary = synthesis_result.get("evidence_summary") or (synthesis_result.get("synthesis_debug") or {}).get("evidence") or []
        block_evidence_summary = [
            {
                "block_id": str(block.get("id") or ""),
                "source_id": str(block.get("source_id") or ""),
                "document_id": str(block.get("document_id") or ""),
                "subject": str(block.get("primary_subject") or ""),
                "space": str(block.get("primary_space") or ", ".join(block.get("space_values") or []) or ""),
                "time": str(block.get("primary_time") or ", ".join(block.get("time_values") or []) or ""),
                "sentence_ids": list(block.get("sentence_ids") or []),
                "claim_ids": list(block.get("claim_ids") or []),
                "summary": str(block.get("summary") or ""),
                "snippet": str(block.get("text") or "")[:500],
                "match_score": block.get("match_score") or 0.0,
                "match_reason": block.get("match_reason") or {},
                "block_status": block.get("block_status") or (block.get("metadata") or {}).get("block_status") or "draft",
                "source_reliability": block.get("source_reliability") or (block.get("metadata") or {}).get("source_reliability") or 0.0,
                "retrieval_weight": block.get("retrieval_weight") or (block.get("metadata") or {}).get("retrieval_weight") or 1.0,
                "conflict_count": block.get("conflict_count") or (block.get("metadata") or {}).get("conflict_count") or 0,
                "conflicts": list(block.get("conflicts") or (block.get("metadata") or {}).get("conflicts") or []),
            }
            for block in matched_semantic_blocks
        ]
        explanation_payload = ExplanationBuilderV0().build(
            answer_text=str(synthesis_result.get("answer_text") or ""),
            matched_claims=matched_claims,
            cited_claim_ids=list(synthesis_result.get("cited_claim_ids") or []),
            cited_sentence_ids=list(synthesis_result.get("cited_sentence_ids") or []),
            cited_source_ids=list(synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or []),
        )
        explanation = explanation_payload.get("explanation") or {}
        verification = verify_answer(str(synthesis_result.get("answer_text") or ""), block_evidence_summary)
        answer_verification = {
            "is_grounded": verification.is_grounded,
            "has_evidence": verification.has_evidence,
            "mentions_conflict": verification.mentions_conflict,
            "invented_terms": list(verification.invented_terms),
            "context_block_count": len(matched_semantic_blocks),
            "warning": None
            if verification.is_grounded or matched_semantic_blocks
            else "A válaszhoz nincs elég erős, visszakövethető bizonyíték.",
        }
        lineage_builder = LineageBuilderV0()
        lineage_graph = lineage_builder.build(global_profiles=query_global_profiles, retrieval_chunks=query_retrieval_chunks)
        lineage_debug = {
            "cited_claims": [
                lineage_builder.focus(lineage_graph, target_type="claim", target_id=str(claim_id))
                for claim_id in synthesis_result.get("cited_claim_ids") or []
            ],
            "matched_profiles": [
                lineage_builder.focus(lineage_graph, target_type="global_profile", target_id=str(chunk.get("profile_id") or ""))
                for chunk in matched_chunks
                if str(chunk.get("profile_id") or "").strip()
            ],
        }
        query_debug = {
            "endpoint_called": "retrieval_service.retrieve",
            "query_text": query,
            "query_profile": query_profile,
            "matched_chunks_count": len(matched_chunks),
            "matched_claims_count": len(matched_claims),
            "matched_semantic_blocks_count": len(matched_semantic_blocks),
            "vector_matched_semantic_blocks_count": len(vector_matched_semantic_blocks),
            "conflict_marker_included": conflict_marker_included,
            "temporal_context_used": bool(query_aware_result.get("temporal_context_used")),
            "synthesis_called": True,
            "answer_text": synthesis_result.get("answer_text") or "",
            "answer_mode": answer_mode,
            "cited_claim_ids": synthesis_result.get("cited_claim_ids") or [],
            "cited_sentence_ids": synthesis_result.get("cited_sentence_ids") or [],
            "cited_source_ids": synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or [],
            "evidence": evidence_summary,
            "context_blocks": block_evidence_summary,
            "explanation": explanation,
            "answer_verification": answer_verification,
            "matched_semantic_blocks": matched_semantic_blocks,
            "lineage": lineage_debug,
            "no_ready_index_build": no_ready_index_build,
            "feedback_events": feedback_events,
            "source_withdrawal_events": source_withdrawal_events,
            "response_contains_answer_text": bool(synthesis_result.get("answer_text")),
        }

        context_text, selected = self._context_builder.build_context(
            query=query,
            hits=hits,
            context_profile=context,
            query_run_id="pending",
        )
        semantic_context_text = self._semantic_blocks_context(matched_semantic_blocks)
        if semantic_context_text:
            context_text = f"{semantic_context_text}\n\n[Vectoros találatok]\n{context_text}" if context_text else semantic_context_text
        citations = [
            Citation(
                source_id=str((item.get("payload") or {}).get("source_id") or ""),
                build_id=str(item.get("build_id") or ""),
                snippet=str((item.get("payload") or {}).get("text") or "")[:400],
                score=float(item.get("fusion_score") or item.get("score") or 0.0),
                title=(item.get("payload") or {}).get("source_title"),
                chunk_id=str((item.get("payload") or {}).get("block_id") or item.get("id") or ""),
                metadata={
                    "profile": item.get("build_key"),
                    "point_type": (item.get("payload") or {}).get("point_type"),
                },
            )
            for item in selected
        ]
        latency_ms = (time.perf_counter() - started) * 1000.0
        query_run = QueryRun(
            tenant=tenant,
            query=query,
            corpus_uuid=corpus_uuid,
            build_ids=[item.id for item in builds],
            retrieval_profile_key=retrieval.key,
            context_profile_key=context.key,
            latency_ms=round(latency_ms, 2),
            result_count=len(hits),
            citations=citations,
            context_text=context_text,
            compare_mode=compare_mode,
            metadata=_json_safe({
                "selected_citation_count": len(citations),
                "query_profile": query_profile,
                "query_detected_entities": query_profile.get("detected_entities") or [],
                "query_intent": query_profile.get("intent") or "unknown",
                "query_filters": {
                    "entity_type": query_profile.get("entity_type"),
                    "entity": query_profile.get("entity"),
                    "state": query_profile.get("state"),
                    "time_filter": query_profile.get("time_filter"),
                    "space_filter": query_profile.get("space_filter"),
                    "keywords": query_profile.get("keywords") or [],
                },
                "query_resolution_confidence": query_profile.get("confidence") or 0.0,
                "no_ready_index_build": no_ready_index_build,
                "query_aware_retrieval": query_aware_result,
                "feedback_events": feedback_events,
                "source_withdrawal_events": source_withdrawal_events,
                "matched_chunks": matched_chunks,
                "matched_claims": matched_claims,
                "matched_semantic_blocks": matched_semantic_blocks,
                "vector_matched_semantic_blocks": vector_matched_semantic_blocks,
                "filtered_out_reason": query_aware_result.get("filtered_out_reason") or [],
                "retrieval_confidence": query_aware_result.get("retrieval_confidence") or 0.0,
                "query_retrieval_match_count": query_aware_result.get("query_retrieval_match_count") or 0,
                "query_retrieval_filtered_count": query_aware_result.get("query_retrieval_filtered_count") or 0,
                "conflict_marker_included": conflict_marker_included,
                "temporal_context_used": bool(query_aware_result.get("temporal_context_used")),
                "synthesis": synthesis_result,
                "synthesis_called": True,
                "answer_text": synthesis_result.get("answer_text") or "",
                "answer_mode": answer_mode,
                "cited_claim_ids": synthesis_result.get("cited_claim_ids") or [],
                "cited_evidence_ids": synthesis_result.get("cited_evidence_ids") or [],
                "cited_sentence_ids": synthesis_result.get("cited_sentence_ids") or [],
                "cited_source_ids": synthesis_result.get("cited_source_ids") or synthesis_result.get("source_ids") or [],
                "source_ids": synthesis_result.get("source_ids") or [],
                "evidence_summary": evidence_summary,
                "context_blocks": block_evidence_summary,
                "explanation": explanation,
                "answer_verification": answer_verification,
                "explanation_payload": explanation_payload,
                "lineage": lineage_debug,
                "synthesis_confidence": synthesis_result.get("synthesis_confidence") or 0.0,
                "query_debug": query_debug,
            }),
        )
        saved = self._query_run_store.save(query_run)
        self._metrics_store.increment("query_count", 1)
        self._metrics_store.record_timing("query_latency_ms", latency_ms)
        self._metrics_store.increment("query_result_count_total", len(hits))
        self._metrics_store.increment("context_char_total", len(context_text))
        self._log_step(
            "query.run.save",
            status="ok",
            tenant=tenant,
            query_run_id=saved.id,
            duration_ms=latency_ms,
            result_count=len(hits),
            build_count=len(builds),
        )
        return saved

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
