from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_processing.enums.ProcessingIssueSeverity import ProcessingIssueSeverity
from apps.kb.kb_processing.service.ProcessingEventService import ProcessingEventService
from apps.kb.kb_processing.service.ProcessingIssueService import ProcessingIssueService
from apps.kb.kb_search.enums.SearchErrorCode import SearchErrorCode

logger = logging.getLogger(__name__)

_SEARCH_MODULE = "kb_search"
_SEARCH_STAGE = "search"

_SEVERITY_BY_CODE: dict[str, ProcessingIssueSeverity] = {
    SearchErrorCode.KB_NOT_READY.value: ProcessingIssueSeverity.WARNING,
    SearchErrorCode.NO_RESULTS.value: ProcessingIssueSeverity.INFO,
    SearchErrorCode.CONTEXT_EMPTY.value: ProcessingIssueSeverity.WARNING,
    SearchErrorCode.QUERY_EMBEDDING_FAILED.value: ProcessingIssueSeverity.ERROR,
    SearchErrorCode.QDRANT_FAILED.value: ProcessingIssueSeverity.ERROR,
    SearchErrorCode.CITATION_BUILD_FAILED.value: ProcessingIssueSeverity.ERROR,
    SearchErrorCode.PERMISSION_DENIED.value: ProcessingIssueSeverity.WARNING,
    SearchErrorCode.TENANT_SCOPE_MISMATCH.value: ProcessingIssueSeverity.ERROR,
}


class SearchIssueRecorderService:
    def __init__(
        self,
        *,
        issue_service: ProcessingIssueService,
        event_service: ProcessingEventService | None = None,
    ) -> None:
        self._issues = issue_service
        self._events = event_service

    def record(
        self,
        *,
        issue_code: str | SearchErrorCode,
        tenant_slug: str | None,
        knowledge_base_id: str,
        message: str | None = None,
        severity: ProcessingIssueSeverity | str | None = None,
        query_run_id: str | None = None,
        conversation_id: str | None = None,
        question: str | None = None,
        search_status: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        code = str(issue_code.value if isinstance(issue_code, SearchErrorCode) else issue_code).strip()
        if not code:
            return
        resolved_severity = severity or _SEVERITY_BY_CODE.get(code, ProcessingIssueSeverity.WARNING)
        issue_metadata = {
            "query_run_id": query_run_id,
            "knowledge_base_id": knowledge_base_id,
            "conversation_id": conversation_id,
            "question": question,
            "search_status": search_status,
            **(metadata or {}),
        }
        self._issues.open_issue(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=None,
            training_item_id=None,
            job_id=query_run_id,
            module=_SEARCH_MODULE,
            stage=_SEARCH_STAGE,
            step=code,
            severity=resolved_severity,
            issue_code=code,
            issue_message=message,
            metadata_json=issue_metadata,
        )
        if self._events is None:
            return
        event_metadata = dict(issue_metadata)
        if resolved_severity in {ProcessingIssueSeverity.ERROR, ProcessingIssueSeverity.CRITICAL}:
            self._events.record_failed(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=None,
                training_item_id=None,
                job_id=query_run_id,
                module=_SEARCH_MODULE,
                stage=_SEARCH_STAGE,
                step=code,
                message=message,
                metadata_json=event_metadata,
            )
        elif code == SearchErrorCode.NO_RESULTS.value:
            self._events.record_completed(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=None,
                training_item_id=None,
                job_id=query_run_id,
                module=_SEARCH_MODULE,
                stage=_SEARCH_STAGE,
                step=code,
                message=message or "Nincs találat a keresésben.",
                metadata_json=event_metadata,
            )
        else:
            self._events.record_skipped(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=None,
                training_item_id=None,
                job_id=query_run_id,
                module=_SEARCH_MODULE,
                stage=_SEARCH_STAGE,
                step=code,
                message=message,
                metadata_json=event_metadata,
            )


__all__ = ["SearchIssueRecorderService"]
