from __future__ import annotations

from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.query_run import Citation, QueryRun
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source


def build_corpus_response(corpus: Corpus, *, can_train: bool | None = None) -> dict[str, object]:
    return {
        "uuid": corpus.uuid,
        "name": corpus.name,
        "description": corpus.description,
        "qdrant_collection_name": corpus.qdrant_collection_name,
        "personal_data_mode": corpus.personal_data_mode,
        "personal_data_sensitivity": corpus.personal_data_sensitivity,
        "created_at": corpus.created_at,
        "updated_at": corpus.updated_at,
        "can_train": can_train,
    }


def build_source_response(source: Source) -> dict[str, object]:
    return {
        "id": source.id,
        "tenant": source.tenant,
        "corpus_uuid": source.corpus_uuid,
        "title": source.title,
        "source_type": source.source_type,
        "status": source.status,
        "file_ref": source.file_ref,
        "created_by": source.created_by,
        "created_at": source.created_at,
        "metadata": source.metadata,
    }


def build_sentence_response(sentence: Sentence) -> dict[str, object]:
    return {
        "id": sentence.id,
        "source_id": sentence.source_id,
        "document_id": sentence.document_id,
        "paragraph_id": sentence.paragraph_id,
        "order_index": sentence.order_index,
        "text_content": sentence.text_content,
        "char_start": sentence.char_start,
        "char_end": sentence.char_end,
        "token_count": sentence.token_count,
        "created_at": sentence.created_at,
        "metadata": sentence.metadata,
    }


def build_paragraph_response(paragraph: Paragraph) -> dict[str, object]:
    return {
        "id": paragraph.id,
        "source_id": paragraph.source_id,
        "document_id": paragraph.document_id,
        "block_id": paragraph.block_id,
        "order_index": paragraph.order_index,
        "text_content": paragraph.text_content,
        "char_start": paragraph.char_start,
        "char_end": paragraph.char_end,
        "sentence_count": paragraph.sentence_count,
        "created_at": paragraph.created_at,
        "metadata": paragraph.metadata,
    }


def build_mention_response(mention: Mention) -> dict[str, object]:
    return {
        "id": mention.id,
        "mention_id": mention.mention_id,
        "sentence_id": mention.sentence_id,
        "mention_type": mention.mention_type,
        "text_content": mention.text_content,
        "surface_text": mention.surface_text,
        "normalized_value": mention.normalized_value,
        "normalized_text": mention.normalized_text,
        "char_start": mention.char_start,
        "char_end": mention.char_end,
        "confidence": mention.confidence,
        "created_at": mention.created_at,
        "metadata": mention.metadata,
    }


def build_claim_response(claim: Claim) -> dict[str, object]:
    return {
        "id": claim.id,
        "sentence_id": claim.sentence_id,
        "subject_text": claim.subject_text,
        "predicate_text": claim.predicate_text,
        "object_text": claim.object_text,
        "claim_type": claim.claim_type,
        "assertion_mode": claim.assertion_mode,
        "time_mode": claim.time_mode,
        "time_label": claim.time_label,
        "space_mode": claim.space_mode,
        "space_label": claim.space_label,
        "confidence": claim.confidence,
        "created_at": claim.created_at,
        "metadata": claim.metadata,
    }


def build_sentence_interpretation_response(item: SentenceInterpretation) -> dict[str, object]:
    return {
        "id": item.id,
        "sentence_id": item.sentence_id,
        "sentence_text": item.sentence_text,
        "claim_summary": item.claim_summary,
        "assertion_mode": item.assertion_mode,
        "claim_type": item.claim_type,
        "time_mode": item.time_mode,
        "time_label": item.time_label,
        "space_mode": item.space_mode,
        "space_label": item.space_label,
        "confidence": item.confidence,
        "information_value_score": item.information_value_score,
        "information_value_status": item.information_value_status,
        "information_value_reason": item.information_value_reason,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "metadata": item.metadata,
    }


def build_ingest_event_response(event: IngestEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "ingest_run_id": event.ingest_run_id,
        "ingest_item_id": event.ingest_item_id,
        "event_type": event.event_type,
        "status": event.status,
        "message": event.message,
        "details": event.details,
        "created_at": event.created_at,
    }


def build_ingest_item_response(item: IngestItem) -> dict[str, object]:
    return {
        "id": item.id,
        "ingest_run_id": item.ingest_run_id,
        "corpus_uuid": item.corpus_uuid,
        "queue_order": item.queue_order,
        "input_type": item.input_type,
        "display_name": item.display_name,
        "title": item.title,
        "origin": item.origin,
        "status": item.status,
        "progress_message": item.progress_message,
        "result_message": item.result_message,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "duplicate_of_item_id": item.duplicate_of_item_id,
        "pipeline_route": item.pipeline_route,
        "content_hash": item.content_hash,
        "source_id": item.source_id,
        "created_at": item.created_at,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "updated_at": item.updated_at,
        "metadata": item.metadata,
    }


def build_ingest_run_response(run: IngestRun, *, items: list[IngestItem] | None = None, events: list[IngestEvent] | None = None) -> dict[str, object]:
    return {
        "id": run.id,
        "corpus_uuid": run.corpus_uuid,
        "input_channel": run.input_channel,
        "status": run.status,
        "batch_size": run.batch_size,
        "queued_count": run.queued_count,
        "processing_count": run.processing_count,
        "completed_count": run.completed_count,
        "failed_count": run.failed_count,
        "duplicate_count": run.duplicate_count,
        "rejected_count": run.rejected_count,
        "continue_on_error": run.continue_on_error,
        "pipeline_route": run.pipeline_route,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "updated_at": run.updated_at,
        "metadata": run.metadata,
        "items": [build_ingest_item_response(item) for item in (items or [])],
        "events": [build_ingest_event_response(event) for event in (events or [])],
    }


def build_index_build_response(build: IndexBuild) -> dict[str, object]:
    return {
        "id": build.id,
        "tenant": build.tenant,
        "corpus_uuid": build.corpus_uuid,
        "index_profile_key": build.index_profile_key,
        "status": build.status,
        "collection_name": build.collection_name,
        "chunk_count": build.chunk_count,
        "error": build.error,
        "created_by": build.created_by,
        "created_at": build.created_at,
        "started_at": build.started_at,
        "completed_at": build.completed_at,
        "metadata": build.metadata,
    }


def build_citation_response(citation: Citation) -> dict[str, object]:
    return {
        "source_id": citation.source_id,
        "build_id": citation.build_id,
        "snippet": citation.snippet,
        "score": citation.score,
        "title": citation.title,
        "chunk_id": citation.chunk_id,
        "metadata": citation.metadata,
    }


def build_query_run_response(query_run: QueryRun) -> dict[str, object]:
    return {
        "id": query_run.id,
        "tenant": query_run.tenant,
        "query": query_run.query,
        "corpus_uuid": query_run.corpus_uuid,
        "build_ids": query_run.build_ids,
        "retrieval_profile_key": query_run.retrieval_profile_key,
        "context_profile_key": query_run.context_profile_key,
        "latency_ms": query_run.latency_ms,
        "result_count": query_run.result_count,
        "citations": [build_citation_response(item) for item in query_run.citations],
        "context_text": query_run.context_text,
        "feedback": query_run.feedback,
        "compare_mode": query_run.compare_mode,
        "created_at": query_run.created_at,
        "metadata": query_run.metadata,
        "query_profile": query_run.metadata.get("query_profile"),
        "matched_chunks": query_run.metadata.get("matched_chunks") or [],
        "matched_claims": query_run.metadata.get("matched_claims") or [],
        "filtered_out_reason": query_run.metadata.get("filtered_out_reason") or [],
        "retrieval_confidence": query_run.metadata.get("retrieval_confidence") or 0.0,
        "query_retrieval_match_count": query_run.metadata.get("query_retrieval_match_count") or 0,
        "query_retrieval_filtered_count": query_run.metadata.get("query_retrieval_filtered_count") or 0,
        "conflict_marker_included": bool(query_run.metadata.get("conflict_marker_included")),
        "temporal_context_used": bool(query_run.metadata.get("temporal_context_used")),
        "answer_text": query_run.metadata.get("answer_text") or "",
        "answer_mode": query_run.metadata.get("answer_mode") or "no_answer",
        "cited_claim_ids": query_run.metadata.get("cited_claim_ids") or [],
        "cited_evidence_ids": query_run.metadata.get("cited_evidence_ids") or [],
        "cited_sentence_ids": query_run.metadata.get("cited_sentence_ids") or [],
        "cited_source_ids": query_run.metadata.get("cited_source_ids") or query_run.metadata.get("source_ids") or [],
        "source_ids": query_run.metadata.get("source_ids") or [],
        "evidence_summary": query_run.metadata.get("evidence_summary") or [],
        "explanation": query_run.metadata.get("explanation") or {},
        "lineage": query_run.metadata.get("lineage") or {},
        "synthesis_confidence": query_run.metadata.get("synthesis_confidence") or 0.0,
        "query_debug": query_run.metadata.get("query_debug") or {},
    }


__all__ = [
    "build_citation_response",
    "build_claim_response",
    "build_corpus_response",
    "build_ingest_event_response",
    "build_ingest_item_response",
    "build_ingest_run_response",
    "build_index_build_response",
    "build_mention_response",
    "build_paragraph_response",
    "build_query_run_response",
    "build_sentence_response",
    "build_sentence_interpretation_response",
    "build_source_response",
]
