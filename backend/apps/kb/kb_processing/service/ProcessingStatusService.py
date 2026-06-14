from __future__ import annotations

from typing import Any, Protocol

from apps.kb.kb_processing.dto.ProcessingEventSummary import ProcessingEventSummary
from apps.kb.kb_processing.dto.ProcessingIssueSummary import ProcessingIssueSummary
from apps.kb.kb_processing.dto.ProcessingListResponses import ProcessingEventsPage, ProcessingIssuesPage
from apps.kb.kb_processing.dto.ProcessingMetricsResponse import ProcessingMetricsResponse
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository
from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from apps.kb.kb_processing.service.ProcessingMetricsService import ProcessingMetricsService


class _OutputEnricher(Protocol):
    def enrich(
        self,
        *,
        module: str,
        step: str,
        training_item_id: str | None,
        output_summary_json: dict[str, Any] | None,
    ) -> dict[str, Any]: ...


class ProcessingStatusService:
    def __init__(
        self,
        metrics_service: ProcessingMetricsService,
        event_repository: ProcessingEventRepository,
        issue_repository: ProcessingIssueRepository,
        *,
        output_enricher: _OutputEnricher | None = None,
    ) -> None:
        self._metrics_service = metrics_service
        self._event_repository = event_repository
        self._issue_repository = issue_repository
        self._output_enricher = output_enricher

    def get_metrics(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None = None,
    ) -> ProcessingMetricsResponse:
        metrics = self._metrics_service.get_for_knowledge_base(knowledge_base_id)
        if metrics is None:
            self._metrics_service.recalculate_for_knowledge_base(
                knowledge_base_id,
                tenant_slug=tenant_slug,
            )
            metrics = self._metrics_service.get_for_knowledge_base(knowledge_base_id)
        if metrics is None:
            from apps.kb.kb_processing.orm.ProcessingMetrics import ProcessingMetrics
            from apps.kb.shared.ids import new_id
            from shared.utils.clock import utc_now_naive

            metrics = ProcessingMetrics(
                id=new_id("proc_metrics"),
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                updated_at=utc_now_naive(),
            )
        return ProcessingMetricsResponse.model_validate(metrics, from_attributes=True)

    def list_events(
        self,
        knowledge_base_id: str,
        *,
        training_item_id: str | None = None,
        job_id: str | None = None,
        module: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ProcessingEventsPage:
        rows = self._event_repository.list_for_knowledge_base(
            knowledge_base_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
            limit=limit,
            offset=offset,
        )
        items = [self._to_event_summary(row) for row in rows]
        total = self._event_repository.count_for_knowledge_base(
            knowledge_base_id,
            training_item_id=training_item_id,
            job_id=job_id,
            module=module,
        )
        return ProcessingEventsPage(items=items, total=total, limit=limit, offset=offset)

    def list_issues(
        self,
        knowledge_base_id: str,
        *,
        training_item_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> ProcessingIssuesPage:
        rows = self._issue_repository.list_for_knowledge_base(
            knowledge_base_id,
            training_item_id=training_item_id,
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

    def _to_event_summary(self, row) -> ProcessingEventSummary:
        summary = ProcessingEventSummary.model_validate(row, from_attributes=True)
        if self._output_enricher is None:
            return summary
        enriched_output = self._output_enricher.enrich(
            module=summary.module,
            step=summary.step,
            training_item_id=summary.training_item_id,
            output_summary_json=summary.output_summary_json,
        )
        if enriched_output == summary.output_summary_json:
            return summary
        return summary.model_copy(update={"output_summary_json": enriched_output})


__all__ = ["ProcessingStatusService"]
