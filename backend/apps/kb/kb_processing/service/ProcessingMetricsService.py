from __future__ import annotations

import logging

from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository

logger = logging.getLogger(__name__)


class ProcessingMetricsService:
    def __init__(
        self,
        metrics_repository: ProcessingMetricsRepository,
        issue_repository: ProcessingIssueRepository,
    ) -> None:
        self._metrics_repository = metrics_repository
        self._issue_repository = issue_repository

    def recalculate_for_knowledge_base(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None = None,
    ) -> None:
        try:
            issue_counts = self._issue_repository.count_open_by_severity(knowledge_base_id)
            metrics = self._metrics_repository.aggregate_for_knowledge_base(
                knowledge_base_id,
                tenant_slug=tenant_slug,
                issue_counts=issue_counts,
            )
            self._metrics_repository.upsert(metrics)
        except Exception:
            logger.warning(
                "Processing metrics recalculate sikertelen (kb=%s)",
                knowledge_base_id,
                exc_info=True,
            )

    def increment_on_ingest(self, knowledge_base_id: str, *, tenant_slug: str | None = None) -> None:
        self.recalculate_for_knowledge_base(knowledge_base_id, tenant_slug=tenant_slug)

    def update_after_understanding(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None = None,
    ) -> None:
        self.recalculate_for_knowledge_base(knowledge_base_id, tenant_slug=tenant_slug)

    def update_after_discovery(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None = None,
    ) -> None:
        self.recalculate_for_knowledge_base(knowledge_base_id, tenant_slug=tenant_slug)

    def update_after_indexing(
        self,
        knowledge_base_id: str,
        *,
        tenant_slug: str | None = None,
    ) -> None:
        self.recalculate_for_knowledge_base(knowledge_base_id, tenant_slug=tenant_slug)

    def get_for_knowledge_base(self, knowledge_base_id: str):
        return self._metrics_repository.get_for_knowledge_base(knowledge_base_id)


__all__ = ["ProcessingMetricsService"]
