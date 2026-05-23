# backend/apps/knowledge/service/knowledge_trace_service.py
# Feladat: Knowledge ingest trace riportot épít futás, dokumentum, mondat, claim, entity és similarity diagnosztikákból. A szolgáltatás az orchestrationt tartja kézben, míg a trace metrikák és nézeti szűrések külön helper modulokba kerültek. Program-specifikus knowledge trace service.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.service.knowledge_trace_view import (
    apply_trace_log_level as _apply_trace_log_level,
    normalize_trace_log_level as _normalize_trace_log_level,
)
from apps.knowledge.service.knowledge_trace_payload_builder import (
    _is_missing_table_error,
    _trace_claim_extraction_fields,
)
from apps.knowledge.service.knowledge_trace_payload_assembler import KnowledgeTracePayloadAssembler
from apps.knowledge.service.knowledge_trace_query_service import KnowledgeTraceQueryService


logger = logging.getLogger(__name__)



class KnowledgeTraceService:
    def __init__(
        self,
        *,
        ingest_run_store,
        ingest_item_store,
        source_store,
        document_store,
        sentence_store,
        mention_store,
        claim_store,
        space_time_frame_store,
        interpretation_run_store=None,
        local_entity_cluster_repository=None,
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._source_store = source_store
        self._document_store = document_store
        self._sentence_store = sentence_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store
        self._interpretation_run_store = interpretation_run_store
        self._local_entity_cluster_repository = local_entity_cluster_repository
        self._query_service = KnowledgeTraceQueryService(
            ingest_run_store=ingest_run_store,
            ingest_item_store=ingest_item_store,
            source_store=source_store,
            document_store=document_store,
            sentence_store=sentence_store,
            mention_store=mention_store,
            claim_store=claim_store,
            space_time_frame_store=space_time_frame_store,
        )
        self._payload_assembler = KnowledgeTracePayloadAssembler(
            local_entity_cluster_repository=local_entity_cluster_repository,
        )

    def build_trace(
        self,
        run_id: str,
        *,
        sentence_limit: int | None = None,
        claim_limit: int | None = None,
        mention_limit: int | None = None,
        log_level: str | None = "FULL_TRACE",
        debug: bool = False,
    ) -> dict[str, Any] | None:
        requested_log_level = _normalize_trace_log_level(log_level, debug=debug)
        query = self._query_service.load(
            run_id,
            sentence_limit=sentence_limit,
            mention_limit=mention_limit,
            claim_limit=claim_limit,
        )
        if query is None:
            return None
        interpretation = self._load_interpretation(run_id, query.document)
        trace = self._payload_assembler.build(query=query, interpretation=interpretation)
        _log_trace(trace)
        return _apply_trace_log_level(trace, requested_log_level)

    def _load_interpretation(self, run_id: str, document: Any | None) -> Any | None:
        if document is None or self._interpretation_run_store is None:
            return None
        try:
            return self._interpretation_run_store.get_for_document(document.id)
        except ProgrammingError as exc:
            if _is_missing_table_error(exc, "knowledge_interpretation_runs"):
                logger.warning(
                    "knowledge.trace.skip_missing_interpretation_runs",
                    extra={"run_id": run_id, "document_id": document.id},
                )
                return None
            raise


def _log_trace(trace: dict[str, Any]) -> None:
    logger.debug(
        "[CLAIM QUALITY DIAGNOSTICS]\nrun_id=%s\nquality_summary=%s",
        trace["run_id"],
        trace["summary"]["quality"],
    )
    logger.debug(
        "[KNOWLEDGE TRACE SERVICE]\nrun_id=%s\nsentence_count=%s\nmention_count=%s\nclaim_count=%s\nspace_time_frame_count=%s\nlocal_entity_cluster_count=%s\nlocal_entity_count=%s\nlow_coherence_local_entity_count=%s\nunknown_entity_type_count=%s",
        trace["run_id"],
        trace["summary"]["sentence_count"],
        trace["summary"]["mention_count"],
        trace["summary"]["claim_count"],
        trace["summary"]["space_time_frame_count"],
        trace["summary"]["local_entity_cluster_count"],
        trace["summary"]["local_entity_count"],
        trace["summary"]["low_coherence_local_entity_count"],
        trace["summary"]["unknown_entity_type_count"],
    )


__all__ = ["KnowledgeTraceService", "_trace_claim_extraction_fields"]
