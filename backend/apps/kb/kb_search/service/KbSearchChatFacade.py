from __future__ import annotations

import json
import logging
from typing import Any

from core.kernel.interface.observability import log_structured_event

from apps.kb.kb_search.repository.SearchCitationRepository import SearchCitationRepository
from apps.kb.kb_search.repository.SearchContextBlockRepository import SearchContextBlockRepository
from apps.kb.kb_search.repository.SearchQueryResultRepository import SearchQueryResultRepository
from apps.kb.kb_search.repository.SearchQueryRunRepository import SearchQueryRunRepository
from apps.kb.kb_search.service.KbSearchPipelineService import KbSearchPipelineService

logger = logging.getLogger(__name__)


class KbSearchChatFacade:
    """Chat modul felé adapter — build_context_for_chat + download API."""

    def __init__(
        self,
        *,
        pipeline: KbSearchPipelineService,
        run_repository: SearchQueryRunRepository,
        result_repository: SearchQueryResultRepository,
        context_block_repository: SearchContextBlockRepository,
        citation_repository: SearchCitationRepository,
        access_checker: Any | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._runs = run_repository
        self._results = result_repository
        self._blocks = context_block_repository
        self._citations = citation_repository
        self._access_checker = access_checker

    async def build_context_for_chat(
        self,
        question: str,
        current_user_id: int | None,
        current_user_role: str | None,
        parsed_query: dict | None,
        kb_uuid: str | None,
        tenant: str | None,
        debug: bool = False,
        conversation_history: list[dict] | None = None,
        channel_id: str | None = None,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        if not kb_uuid:
            return self._empty_packet(answer_mode="NO_ANSWER")
        if current_user_id is not None and not self._can_use_kb(kb_uuid, current_user_id, current_user_role):
            from apps.chat.errors import ChatPermissionDenied

            raise ChatPermissionDenied("Nincs jogosultság a megadott tudástár használatához.")

        log_structured_event(
            "apps.kb.kb_search",
            "CHAT_CONTEXT_BUILT",
            kb_uuid=kb_uuid,
            user_id=current_user_id,
        )
        packet = self._pipeline.execute(
            question=question,
            knowledge_base_id=kb_uuid,
            kb_uuid=kb_uuid,
            tenant_slug=tenant,
            user_id=current_user_id,
            channel_id=channel_id,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            debug=debug,
        )
        if parsed_query:
            packet.setdefault("query_focus", parsed_query)
        return packet

    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict | None:
        citation = self._citations.get_by_source_id(query_run_id, source_id)
        if citation is None:
            rows = self._citations.list_for_run(query_run_id)
            citation = next((row for row in rows if row.citation_id == source_id or row.chunk_id == source_id), None)
        if citation is None:
            return None
        run = self._runs.get(query_run_id)
        body = "\n".join(
            [
                f"Citation: {citation.citation_id}",
                f"Dokumentum: {citation.document_title}",
                f"Oldal: {', '.join(str(p) for p in (citation.page_numbers or []))}",
                f"Szekció: {citation.section_title or '—'}",
                "",
                citation.snippet or "",
            ]
        ).encode("utf-8")
        return {
            "body": body,
            "filename": f"source-{citation.citation_id}.txt",
            "content_type": "text/plain; charset=utf-8",
            "corpus_uuid": run.kb_uuid if run else "",
        }

    def get_query_context_download(self, query_run_id: str) -> dict | None:
        run = self._runs.get(query_run_id)
        if run is None:
            return None
        blocks = self._blocks.list_for_run(query_run_id)
        citations = self._citations.list_for_run(query_run_id)
        results = self._results.list_for_run(query_run_id)
        payload = {
            "question": run.question,
            "normalized_question": run.normalized_question,
            "conversation_id": run.conversation_id,
            "knowledge_base_id": run.knowledge_base_id,
            "search_results": [
                {
                    "rank": row.rank,
                    "chunk_id": row.chunk_id,
                    "qdrant_score": row.qdrant_score,
                    "hybrid_score": row.hybrid_score,
                    "overall_score": row.overall_score,
                }
                for row in results
            ],
            "context_blocks": [
                {
                    "context_block_id": block.context_block_id,
                    "text": block.text,
                    "snippet": block.snippet,
                    "section_title": block.section_title,
                    "page_numbers": block.page_numbers,
                }
                for block in blocks
            ],
            "citations": [
                {
                    "citation_id": row.citation_id,
                    "document_title": row.document_title,
                    "snippet": row.snippet,
                }
                for row in citations
            ],
            "timestamps": {
                "created_at": run.created_at.isoformat() if run.created_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            },
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return {
            "body": body,
            "filename": f"context-{query_run_id[:12]}.json",
            "content_type": "application/json; charset=utf-8",
            "corpus_uuid": run.kb_uuid,
        }

    def _can_use_kb(self, kb_uuid: str, user_id: int, user_role: str | None) -> bool:
        checker = self._access_checker
        if checker is None:
            return True
        if hasattr(checker, "user_can_use"):
            try:
                result = checker.user_can_use(kb_uuid, user_id, type("S", (), {"id": user_id, "role": user_role, "is_active": True})())
                if hasattr(result, "__await__"):
                    return False
                return bool(result)
            except TypeError:
                return bool(checker.user_can_use(kb_uuid, user_id))
        return True

    @staticmethod
    def _empty_packet(*, answer_mode: str) -> dict[str, Any]:
        return {
            "query_run_id": None,
            "answer_mode": answer_mode,
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
        }


__all__ = ["KbSearchChatFacade"]
