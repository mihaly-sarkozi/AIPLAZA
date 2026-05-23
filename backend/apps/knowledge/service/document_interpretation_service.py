# backend/apps/knowledge/service/document_interpretation_service.py
# Orchestrates sentence interpretation without keeping the workflow inside KnowledgeFacade.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import logging
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.domain.candidate_selection import entity_candidate_to_json_dict
from apps.knowledge.domain.decision_analysis import decision_analysis_to_json_dict
from apps.knowledge.domain.search_profile import search_profile_to_json_dict
from apps.knowledge.domain.semantic_block import semantic_block_to_json_dict
from apps.knowledge.domain.similarity_analysis import similarity_analysis_to_json_dict
from apps.knowledge.domain.technical_entity import technical_entity_to_json_dict
from apps.knowledge.domain.technical_memory_chunk import technical_memory_chunk_to_json_dict
from apps.knowledge.domain.tension_analysis import tension_analysis_to_json_dict
from apps.knowledge.service.candidate_selection_v1 import CandidateSelectionV1, candidate_selection_attempt_count
from apps.knowledge.service.decision_engine_v1 import DecisionEngineV1
from apps.knowledge.service.facade_helpers import (
    empty_claim_quality_summary,
    merge_claim_quality_summary,
    utcnow,
)
from apps.knowledge.service.global_profile_builder_v0 import GlobalProfileBuilderV0
from apps.knowledge.service.local_resolver_v1 import attach_local_resolver_metadata
from apps.knowledge.service.retrieval_chunk_builder_v0 import RetrievalChunkBuilderV0
from apps.knowledge.service.search_profile_builder_v1 import SearchProfileBuilderV1
from apps.knowledge.service.semantic_block_builder_v1 import SemanticBlockBuilderV1
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality
from apps.knowledge.service.similarity_engine_v1 import SimilarityEngineV1
from apps.knowledge.service.subject_context_resolver_v1 import SubjectContextResolverV1
from apps.knowledge.service.technical_entity_builder_v1 import TechnicalEntityBuilderV1
from apps.knowledge.service.technical_memory_chunk_builder_v1 import TechnicalMemoryChunkBuilderV1
from apps.knowledge.service.tension_engine_v1 import TensionEngineV1

logger = logging.getLogger(__name__)


class DocumentInterpretationService:
    def __init__(
        self,
        *,
        interpretation_run_store: Any | None,
        sentence_interpretation_store: Any | None,
        mention_store: Any | None,
        claim_store: Any | None,
        space_time_frame_store: Any | None,
        build_sentence_mentions: Callable[..., list[Mention]],
        resolve_sentence_language: Callable[..., str],
        build_sentence_claim_payload: Callable[..., tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]],
        finalize_sentence_after_subject_context: Callable[..., tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]],
        resolve_and_persist_local_entity_clusters: Callable[..., tuple[list[Any], dict[str, Any]]],
        load_existing_semantic_blocks: Callable[..., list[dict[str, Any]]],
        load_existing_search_profiles: Callable[..., list[Any]],
        load_existing_global_profiles: Callable[..., list[Any]],
        is_missing_table_error: Callable[..., bool],
        truncate_error_message: Callable[..., str],
        interpretation_error_message_max: int,
    ) -> None:
        self._interpretation_run_store = interpretation_run_store
        self._sentence_interpretation_store = sentence_interpretation_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store
        self._build_sentence_mentions = build_sentence_mentions
        self._resolve_sentence_language = resolve_sentence_language
        self._build_sentence_claim_payload = build_sentence_claim_payload
        self._finalize_sentence_after_subject_context = finalize_sentence_after_subject_context
        self._resolve_and_persist_local_entity_clusters = resolve_and_persist_local_entity_clusters
        self._load_existing_semantic_blocks = load_existing_semantic_blocks
        self._load_existing_search_profiles = load_existing_search_profiles
        self._load_existing_global_profiles = load_existing_global_profiles
        self._is_missing_table_error = is_missing_table_error
        self._truncate_error_message = truncate_error_message
        self._interpretation_error_message_max = interpretation_error_message_max

    def interpret_document(
        self,
        *,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> InterpretationRun | None:
        if (
            self._interpretation_run_store is None
            or self._sentence_interpretation_store is None
            or self._mention_store is None
            or self._claim_store is None
        ):
            if progress_callback is not None:
                progress_callback(
                    "interpretation_skipped",
                    {"reason": "stores_unavailable", "total_sentences": len(sentences)},
                )
            return None

        try:
            existing_run = self._interpretation_run_store.get_for_document(document.id)
        except ProgrammingError as exc:
            if self._is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
                "knowledge_space_time_frames",
            ):
                logger.warning(
                    "knowledge.interpretation.skip_missing_tables",
                    extra={"document_id": document.id, "source_id": source.id, "corpus_uuid": source.corpus_uuid},
                )
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_skipped",
                        {"reason": "missing_tables", "total_sentences": len(sentences)},
                    )
                return None
            raise
        if existing_run is not None:
            if progress_callback is not None:
                progress_callback(
                    "interpretation_completed",
                    {
                        "interpretation_run_id": existing_run.id,
                        "processed_sentences": int(existing_run.metadata.get("sentence_interpretation_count") or len(sentences)),
                        "total_sentences": int(existing_run.metadata.get("sentence_count") or len(sentences)),
                        "mention_count": int(existing_run.metadata.get("mention_count") or 0),
                        "claim_count": int(existing_run.metadata.get("claim_count") or 0),
                        "local_entity_cluster_count": int(existing_run.metadata.get("local_entity_cluster_count") or 0),
                        "quality": dict(existing_run.metadata.get("quality_summary") or {}),
                    },
                )
            return existing_run

        run: InterpretationRun | None = None
        try:
            run = self._interpretation_run_store.create(
                InterpretationRun(
                    tenant=source.tenant,
                    corpus_uuid=source.corpus_uuid,
                    source_id=source.id,
                    document_id=document.id,
                    status="processing",
                    created_by=created_by,
                    started_at=utcnow(),
                    metadata={"sentence_count": len(sentences)},
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_started",
                    {
                        "interpretation_run_id": run.id,
                        "processed_sentences": 0,
                        "total_sentences": len(sentences),
                    },
                )
            mentions: list[Mention] = []
            quality_summary = empty_claim_quality_summary()
            staged: list[tuple[Sentence, list[Mention], SentenceInterpretation, str, list[Claim]]] = []
            for index, sentence in enumerate(sentences, start=1):
                sentence_mentions = self._build_sentence_mentions(sentence, source=source, document=document)
                sentence_language = self._resolve_sentence_language(sentence, source=source, document=document)
                sentence_interpretation, sentence_claims, _ = self._build_sentence_claim_payload(
                    sentence,
                    sentence_mentions,
                    source=source,
                    document=document,
                    defer_space_time=True,
                )
                sentence_interpretation = replace(sentence_interpretation, interpretation_run_id=run.id)
                sentence_mentions = [replace(item, interpretation_run_id=run.id) for item in sentence_mentions]
                sentence_claims = [replace(item, interpretation_run_id=run.id) for item in sentence_claims]
                quality_summary = merge_claim_quality_summary(
                    quality_summary,
                    dict(sentence_interpretation.metadata.get("quality_gate") or {}),
                )
                staged.append((sentence, sentence_mentions, sentence_interpretation, sentence_language, sentence_claims))
                mentions.extend(sentence_mentions)
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_progress",
                        {
                            "interpretation_run_id": run.id,
                            "processed_sentences": index,
                            "total_sentences": len(sentences),
                        },
                    )

            subject_context_payload: list[dict[str, Any]] = [
                {
                    "sentence_id": s.id,
                    "order_index": s.order_index,
                    "text": s.text_content,
                    "language": lang,
                    "mentions": sm,
                    "claims": sc,
                }
                for s, sm, _interp, lang, sc in staged
            ]
            resolved_subject_rows = SubjectContextResolverV1().resolve_claims(subject_context_payload)
            resolved_by_sid = {str(r.get("sentence_id") or ""): r for r in resolved_subject_rows}

            interpretations: list[SentenceInterpretation] = []
            claims: list[Claim] = []
            space_time_frames: list[SpaceTimeFrame] = []
            for sentence, sentence_mentions, sentence_interpretation, sentence_language, _ in staged:
                row = resolved_by_sid.get(str(sentence.id))
                sentence_claims = list((row or {}).get("claims") or [])
                interp_out, claims_out, frames_out = self._finalize_sentence_after_subject_context(
                    sentence,
                    sentence_mentions,
                    sentence_interpretation,
                    sentence_claims,
                    language=sentence_language,
                    source=source,
                    document=document,
                )
                interpretations.append(interp_out)
                claims.extend(claims_out)
                space_time_frames.extend(frames_out)

            created_interpretations = self._sentence_interpretation_store.create_many(interpretations)
            self._mention_store.create_many(mentions)
            self._claim_store.create_many(claims)
            if self._space_time_frame_store is not None:
                self._space_time_frame_store.create_many(space_time_frames)
            local_clusters, local_resolver_trace = self._resolve_and_persist_local_entity_clusters(
                run=run,
                source=source,
                document=document,
                sentences=sentences,
                mentions=mentions,
                claims=claims,
            )
            semantic_blocks = SemanticBlockBuilderV1().build(sentences=sentences, claims=claims)
            semantic_block_payload = [semantic_block_to_json_dict(item) for item in semantic_blocks]
            semantic_block_payload = enrich_semantic_blocks_with_quality(
                semantic_block_payload,
                existing_blocks=self._load_existing_semantic_blocks(
                    corpus_uuid=source.corpus_uuid,
                    exclude_interpretation_run_id=run.id,
                ),
                source_type=source.source_type,
            )
            technical_entities = TechnicalEntityBuilderV1().build(local_clusters, claims=claims)
            technical_entity_payload = [technical_entity_to_json_dict(item) for item in technical_entities]
            technical_memory_chunks = TechnicalMemoryChunkBuilderV1().build_many(technical_entities)
            technical_memory_chunk_payload = [
                technical_memory_chunk_to_json_dict(item) for item in technical_memory_chunks
            ]
            search_profiles = SearchProfileBuilderV1().build_many(technical_memory_chunks)
            search_profile_payload = [search_profile_to_json_dict(item) for item in search_profiles]
            stored_search_profiles = self._load_existing_search_profiles(
                corpus_uuid=source.corpus_uuid,
                exclude_interpretation_run_id=run.id,
            )
            stored_global_profiles = self._load_existing_global_profiles(
                corpus_uuid=source.corpus_uuid,
                exclude_interpretation_run_id=run.id,
            )
            candidate_profile_pool = stored_search_profiles or search_profiles
            candidate_selection_attempted_count = candidate_selection_attempt_count(
                search_profiles,
                existing_profiles=stored_search_profiles if stored_search_profiles else None,
            )
            candidate_pool_size = len(candidate_profile_pool)
            candidate_selections = CandidateSelectionV1().select_many(
                search_profiles,
                existing_profiles=stored_search_profiles if stored_search_profiles else None,
                limit_per_profile=3,
            )
            candidate_selection_payload = [entity_candidate_to_json_dict(item) for item in candidate_selections]
            similarity_analyses = SimilarityEngineV1().analyze_many(
                search_profiles,
                candidate_selections,
                candidate_profile_pool,
            )
            similarity_analysis_payload = [similarity_analysis_to_json_dict(item) for item in similarity_analyses]
            decision_analyses = DecisionEngineV1().decide_many(
                search_profiles,
                candidate_selections,
                similarity_analyses,
                tensions=[],
            )
            decision_analysis_payload = [decision_analysis_to_json_dict(item) for item in decision_analyses]
            global_profiles = GlobalProfileBuilderV0().build_many(
                decision_analyses,
                search_profiles,
                candidate_profiles=candidate_profile_pool,
                existing_global_profiles=stored_global_profiles,
            )
            tension_analyses = [
                *TensionEngineV1().analyze_many(
                    search_profiles,
                    similarity_analyses,
                    candidate_profile_pool,
                ),
                *TensionEngineV1().analyze_global_profiles(global_profiles),
            ]
            tension_analysis_payload = [tension_analysis_to_json_dict(item) for item in tension_analyses]
            retrieval_chunks = RetrievalChunkBuilderV0().build_many(
                global_profiles,
                tension_analysis_payload,
            )
            completed_run = self._interpretation_run_store.update(
                replace(
                    run,
                    status="completed",
                    language=document.language,
                    completed_at=utcnow(),
                    updated_at=utcnow(),
                    metadata=attach_local_resolver_metadata(
                        {
                            **run.metadata,
                            "sentence_interpretation_count": len(created_interpretations),
                            "mention_count": len(mentions),
                            "claim_count": len(claims),
                            "space_time_frame_count": len(space_time_frames),
                            "quality_summary": quality_summary,
                            "semantic_block_builder_version": SemanticBlockBuilderV1.version,
                            "semantic_block_count": len(semantic_blocks),
                            "semantic_blocks": semantic_block_payload,
                            "semantic_block_conflict_count": sum(int(item.get("conflict_count") or 0) for item in semantic_block_payload),
                            "semantic_block_disputed_count": sum(1 for item in semantic_block_payload if item.get("block_status") == "disputed"),
                            "technical_entity_builder_version": TechnicalEntityBuilderV1.version,
                            "technical_entity_count": len(technical_entities),
                            "technical_entities": technical_entity_payload,
                            "technical_memory_chunk_builder_version": TechnicalMemoryChunkBuilderV1.version,
                            "technical_memory_chunk_count": len(technical_memory_chunks),
                            "technical_memory_chunks": technical_memory_chunk_payload,
                            "search_profile_builder_version": SearchProfileBuilderV1.version,
                            "search_profile_count": len(search_profiles),
                            "search_profiles": search_profile_payload,
                            "candidate_selection_builder_version": CandidateSelectionV1.version,
                            "candidate_selection_attempted_count": candidate_selection_attempted_count,
                            "candidate_pool_size": candidate_pool_size,
                            "candidate_selection_count": len(candidate_selections),
                            "candidate_selections": candidate_selection_payload,
                            "similarity_engine_version": SimilarityEngineV1.version,
                            "similarity_analysis_count": len(similarity_analyses),
                            "similarity_analyses": similarity_analysis_payload,
                            "tension_engine_version": TensionEngineV1.version,
                            "tension_analysis_count": len(tension_analyses),
                            "tension_analyses": tension_analysis_payload,
                            "retrieval_chunk_builder_version": RetrievalChunkBuilderV0.version,
                            "retrieval_chunk_count": len(retrieval_chunks),
                            "retrieval_chunks": retrieval_chunks,
                            "decision_engine_version": DecisionEngineV1.version,
                            "decision_analysis_count": len(decision_analyses),
                            "decision_analyses": decision_analysis_payload,
                            "global_profile_builder_version": GlobalProfileBuilderV0.version,
                            "global_profile_count": len(global_profiles),
                            "global_profiles": global_profiles,
                        },
                        clusters=local_clusters,
                        trace=local_resolver_trace,
                    ),
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_completed",
                    {
                        "interpretation_run_id": completed_run.id,
                        "processed_sentences": len(created_interpretations),
                        "total_sentences": len(sentences),
                        "mention_count": len(mentions),
                        "claim_count": len(claims),
                        "local_entity_cluster_count": len(local_clusters),
                        "quality": quality_summary,
                    },
                )
            return completed_run
        except ProgrammingError as exc:
            if self._is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
            ):
                logger.warning(
                    "knowledge.interpretation.skip_missing_tables",
                    extra={"document_id": document.id, "source_id": source.id, "corpus_uuid": source.corpus_uuid},
                )
                if progress_callback is not None:
                    progress_callback(
                        "interpretation_skipped",
                        {"reason": "missing_tables", "total_sentences": len(sentences)},
                    )
                return None
            raise
        except Exception as exc:
            if run is None:
                return None
            failed_run = self._interpretation_run_store.update(
                replace(
                    run,
                    status="failed",
                    error_message=self._truncate_error_message(
                        exc,
                        max_length=self._interpretation_error_message_max,
                    ),
                    completed_at=utcnow(),
                    updated_at=utcnow(),
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_failed",
                    {
                        "interpretation_run_id": failed_run.id,
                        "processed_sentences": int(failed_run.metadata.get("sentence_interpretation_count") or 0),
                        "total_sentences": len(sentences),
                        "error_message": failed_run.error_message,
                    },
                )
            return failed_run


__all__ = ["DocumentInterpretationService"]
