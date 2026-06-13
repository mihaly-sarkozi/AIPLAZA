from __future__ import annotations

from apps.kb.kb_processing.dto.ProcessingEventSummary import ProcessingEventSummary
from apps.kb.kb_processing.dto.ProcessingIssueSummary import ProcessingIssueSummary
from apps.kb.kb_processing.dto.ProcessingListResponses import ProcessingEventsPage, ProcessingIssuesPage
from apps.kb.kb_processing.dto.ProcessingMetricsResponse import ProcessingMetricsResponse
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository
from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from apps.kb.kb_processing.service.ProcessingMetricsService import ProcessingMetricsService


class ProcessingStatusService:
    def __init__(
        self,
        metrics_service: ProcessingMetricsService,
        event_repository: ProcessingEventRepository,
        issue_repository: ProcessingIssueRepository,
    ) -> None:
        self._metrics_service = metrics_service
        self._event_repository = event_repository
        self._issue_repository = issue_repository

    def get_metrics(self, knowledge_base_id: str) -> ProcessingMetricsResponse | None:
        metrics = self._metrics_service.get_for_knowledge_base(knowledge_base_id)
        if metrics is None:
            return None
        return ProcessingMetricsResponse.model_validate(metrics, from_attributes=True)

    def list_events(
        self,
        knowledge_base_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> ProcessingEventsPage:
        rows = self._event_repository.list_for_knowledge_base(
            knowledge_base_id,
            limit=limit,
            offset=offset,
        )
        items = [
            ProcessingEventSummary.model_validate(row, from_attributes=True)
            for row in rows
        ]
        total = self._event_repository.count_for_knowledge_base(knowledge_base_id)
        return ProcessingEventsPage(items=items, total=total, limit=limit, offset=offset)

    def list_issues(
        self,
        knowledge_base_id: str,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ProcessingIssuesPage:
        rows = self._issue_repository.list_for_knowledge_base(
            knowledge_base_id,
            status=status,
            severity=severity,
            limit=limit,
            offset=offset,
        )
        items = [
            ProcessingIssueSummary.model_validate(row, from_attributes=True)
            for row in rows
        ]
        return ProcessingIssuesPage(items=items, total=len(items), limit=limit, offset=offset)


__all__ = ["ProcessingStatusService"]
