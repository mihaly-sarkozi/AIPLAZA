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
from apps.knowledge.service.facade_helpers import utcnow
from apps.knowledge.service.interpretation_artifact_builder import InterpretationArtifactBuilder
from apps.knowledge.service.sentence_interpretation_workflow import SentenceInterpretationWorkflow

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
        self._resolve_and_persist_local_entity_clusters = resolve_and_persist_local_entity_clusters
        self._is_missing_table_error = is_missing_table_error
        self._truncate_error_message = truncate_error_message
        self._interpretation_error_message_max = interpretation_error_message_max
        self._artifact_builder = InterpretationArtifactBuilder(
            load_existing_semantic_blocks=load_existing_semantic_blocks,
            load_existing_search_profiles=load_existing_search_profiles,
            load_existing_global_profiles=load_existing_global_profiles,
        )
        self._sentence_workflow = SentenceInterpretationWorkflow(
            build_sentence_mentions=build_sentence_mentions,
            resolve_sentence_language=resolve_sentence_language,
            build_sentence_claim_payload=build_sentence_claim_payload,
            finalize_sentence_after_subject_context=finalize_sentence_after_subject_context,
        )

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
            sentence_result = self._sentence_workflow.run(
                run_id=run.id,
                source=source,
                document=document,
                sentences=sentences,
                progress_callback=progress_callback,
            )
            created_interpretations = self._sentence_interpretation_store.create_many(sentence_result.interpretations)
            self._mention_store.create_many(sentence_result.mentions)
            self._claim_store.create_many(sentence_result.claims)
            if self._space_time_frame_store is not None:
                self._space_time_frame_store.create_many(sentence_result.space_time_frames)
            local_clusters, local_resolver_trace = self._resolve_and_persist_local_entity_clusters(
                run=run,
                source=source,
                document=document,
                sentences=sentences,
                mentions=sentence_result.mentions,
                claims=sentence_result.claims,
            )
            artifacts = self._artifact_builder.build_metadata(
                run=run,
                source=source,
                document=document,
                sentences=sentences,
                claims=sentence_result.claims,
                local_clusters=local_clusters,
                local_resolver_trace=local_resolver_trace,
                sentence_interpretation_count=len(created_interpretations),
                mention_count=len(sentence_result.mentions),
                space_time_frame_count=len(sentence_result.space_time_frames),
                quality_summary=sentence_result.quality_summary,
            )
            completed_run = self._interpretation_run_store.update(
                replace(
                    run,
                    status="completed",
                    language=document.language,
                    completed_at=utcnow(),
                    updated_at=utcnow(),
                    metadata=artifacts.metadata,
                )
            )
            if progress_callback is not None:
                progress_callback(
                    "interpretation_completed",
                    {
                        "interpretation_run_id": completed_run.id,
                        "processed_sentences": len(created_interpretations),
                        "total_sentences": len(sentences),
                        "mention_count": len(sentence_result.mentions),
                        "claim_count": len(sentence_result.claims),
                        "local_entity_cluster_count": artifacts.local_entity_cluster_count,
                        "quality": sentence_result.quality_summary,
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
