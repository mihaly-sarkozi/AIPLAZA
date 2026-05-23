from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.service.language_rules import resolve_language
from apps.knowledge.service.knowledge_trace_payload_builder import (
    _bump_subject_context_counters,
    _fallback_space_time_frame_for_claim,
    _is_missing_table_error,
    _lower_sentence_initial_time_value,
    _trace_claim_extraction_fields,
    _trace_subject_context_claim_report_fields,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KnowledgeTraceQueryResult:
    run: Any
    items: list[Any]
    primary_item: Any | None
    source_id: str
    source: Any | None
    document: Any | None
    sentences: list[Any]
    sentence_rows: list[dict[str, Any]]
    total_mentions: int
    total_claims: int
    total_space_time_frames: int
    negative_claim_count: int
    subj_ctx_counters: dict[str, int]
    language: str | None


class KnowledgeTraceQueryService:
    def __init__(
        self,
        *,
        ingest_run_store: Any,
        ingest_item_store: Any,
        source_store: Any,
        document_store: Any,
        sentence_store: Any,
        mention_store: Any,
        claim_store: Any,
        space_time_frame_store: Any,
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._source_store = source_store
        self._document_store = document_store
        self._sentence_store = sentence_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store

    def load(
        self,
        run_id: str,
        *,
        sentence_limit: int | None,
        mention_limit: int | None,
        claim_limit: int | None,
    ) -> KnowledgeTraceQueryResult | None:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            return None
        items = self._ingest_item_store.list_for_run(run_id)
        primary_item = next((item for item in items if item.source_id), items[0] if items else None)
        source_id = str(primary_item.source_id or "") if primary_item is not None else ""
        source = self._source_store.get(source_id) if source_id else None
        document = self._document_store.get_for_source(source_id) if source_id else None
        sentences = self._sentence_store.list_for_document(document.id) if document is not None else []
        sentences = sorted(sentences, key=lambda item: (item.order_index, item.char_start, item.created_at))
        if sentence_limit is not None:
            sentences = sentences[:sentence_limit]

        sentence_rows, totals, counters = self._build_sentence_rows(
            run_id=run_id,
            sentences=sentences,
            mention_limit=mention_limit,
            claim_limit=claim_limit,
        )
        language = (
            getattr(document, "language", None)
            or (source.metadata.get("language") if source is not None and isinstance(source.metadata, dict) else None)
            or resolve_language(text="\n".join(item.text_content for item in sentences))
        )
        return KnowledgeTraceQueryResult(
            run=run,
            items=items,
            primary_item=primary_item,
            source_id=source_id,
            source=source,
            document=document,
            sentences=sentences,
            sentence_rows=sentence_rows,
            total_mentions=totals["mentions"],
            total_claims=totals["claims"],
            total_space_time_frames=totals["space_time_frames"],
            negative_claim_count=totals["negative_claims"],
            subj_ctx_counters=counters,
            language=language,
        )

    def _build_sentence_rows(
        self,
        *,
        run_id: str,
        sentences: list[Any],
        mention_limit: int | None,
        claim_limit: int | None,
    ) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
        sentence_rows: list[dict[str, Any]] = []
        totals = {"mentions": 0, "claims": 0, "space_time_frames": 0, "negative_claims": 0}
        sentence_id_to_order = {str(s.id): int(s.order_index) for s in sentences}
        counters = {
            "applied": 0,
            "skipped": 0,
            "reset": 0,
            "weak_subject_override": 0,
            "blocked": 0,
            "source_phrase_stripped": 0,
            "suffix_normalized": 0,
            "missing_subject_error": 0,
            "explicit_subject_kept": 0,
            "temporal_subject_sanitized": 0,
            "weak_auxiliary_subject_stripped": 0,
            "duplicate_weak_compatible": 0,
        }
        remaining_mentions = mention_limit
        remaining_claims = claim_limit
        for sentence in sentences:
            row, remaining_mentions, remaining_claims = self._build_sentence_row(
                run_id=run_id,
                sentence=sentence,
                sentence_id_to_order=sentence_id_to_order,
                counters=counters,
                remaining_mentions=remaining_mentions,
                remaining_claims=remaining_claims,
                totals=totals,
            )
            sentence_rows.append(row)
        return sentence_rows, totals, counters

    def _build_sentence_row(
        self,
        *,
        run_id: str,
        sentence: Any,
        sentence_id_to_order: dict[str, int],
        counters: dict[str, int],
        remaining_mentions: int | None,
        remaining_claims: int | None,
        totals: dict[str, int],
    ) -> tuple[dict[str, Any], int | None, int | None]:
        mentions = self._mention_store.list_for_sentence(sentence.id) if self._mention_store is not None else []
        claims = self._claim_store.list_for_sentence(sentence.id) if self._claim_store is not None else []
        frames = self._list_frames(run_id, sentence.id)
        mentions = sorted(mentions, key=lambda item: (item.char_start, item.char_end, item.created_at))
        claims = sorted(claims, key=lambda item: (item.created_at, item.claim_id))
        frame_by_claim_id = {item.claim_id: item for item in frames if item.claim_id}
        if remaining_mentions is not None:
            mentions = mentions[: max(0, remaining_mentions)]
            remaining_mentions = max(0, remaining_mentions - len(mentions))
        if remaining_claims is not None:
            claims = claims[: max(0, remaining_claims)]
            remaining_claims = max(0, remaining_claims - len(claims))
        for item in claims:
            _bump_subject_context_counters(item, counters)
            if str(getattr(item, "assertion_mode", "") or "") == "negation":
                totals["negative_claims"] += 1
        totals["mentions"] += len(mentions)
        totals["claims"] += len(claims)
        totals["space_time_frames"] += len(frames)
        return (
            {
                "sentence_id": sentence.id,
                "order_index": sentence.order_index,
                "text": sentence.text_content,
                "language": (
                    (sentence.metadata.get("language") if isinstance(sentence.metadata, dict) else None)
                    or resolve_language(text=sentence.text_content)
                ),
                "mentions": [self._mention_row(item) for item in mentions],
                "claims": [
                    self._claim_row(item, frame_by_claim_id, sentence_id_to_order=sentence_id_to_order)
                    for item in claims
                ],
            },
            remaining_mentions,
            remaining_claims,
        )

    def _list_frames(self, run_id: str, sentence_id: str) -> list[Any]:
        if self._space_time_frame_store is None:
            return []
        try:
            return self._space_time_frame_store.list_for_sentence(sentence_id)
        except ProgrammingError as exc:
            if _is_missing_table_error(exc, "knowledge_space_time_frames"):
                logger.warning(
                    "knowledge.trace.skip_missing_space_time_frames",
                    extra={"run_id": run_id, "sentence_id": sentence_id},
                )
                return []
            raise

    @staticmethod
    def _mention_row(item: Any) -> dict[str, Any]:
        return {
            "mention_id": item.mention_id,
            "surface_text": item.surface_text,
            "normalized_text": item.normalized_text,
            "mention_type": item.mention_type,
            "char_start": item.char_start,
            "char_end": item.char_end,
            "confidence": item.confidence,
        }

    @staticmethod
    def _claim_row(
        item: Any,
        frame_by_claim_id: dict[str, Any],
        *,
        sentence_id_to_order: dict[str, int],
    ) -> dict[str, Any]:
        frame = frame_by_claim_id.get(item.claim_id)
        return {
            "claim_id": item.claim_id,
            "claim_text": item.claim_text,
            "subject_text": item.subject_text,
            "predicate": item.predicate,
            "object_text": item.object_text,
            **_trace_claim_extraction_fields(item),
            **_trace_subject_context_claim_report_fields(item, sentence_id_to_order=sentence_id_to_order),
            "claim_type": item.claim_type,
            "claim_group": item.claim_group,
            "claim_status": item.claim_status,
            "confidence": item.confidence,
            "identity_weight": item.identity_weight,
            "similarity_weight": item.similarity_weight,
            "tension_weight": item.tension_weight,
            "conflict_behavior": item.conflict_behavior,
            "cardinality": item.cardinality,
            "time_mode": item.time_mode or (frame.time_mode if frame is not None else "unknown"),
            "space_mode": item.space_mode or (frame.space_mode if frame is not None else "unknown"),
            "space_time_frame": KnowledgeTraceQueryService._frame_row(frame)
            if frame is not None
            else _fallback_space_time_frame_for_claim(item),
        }

    @staticmethod
    def _frame_row(frame: Any) -> dict[str, Any]:
        return {
            "frame_id": frame.frame_id,
            "time_mode": frame.time_mode,
            "time_value": _lower_sentence_initial_time_value(frame.time_value),
            "time_start": frame.time_start,
            "time_end": frame.time_end,
            "time_precision": frame.time_precision,
            "time_confidence": frame.time_confidence,
            "space_mode": frame.space_mode,
            "space_value": frame.space_value,
            "space_precision": frame.space_precision,
            "space_confidence": frame.space_confidence,
            "overall_confidence": frame.overall_confidence,
        }


__all__ = ["KnowledgeTraceQueryResult", "KnowledgeTraceQueryService"]
