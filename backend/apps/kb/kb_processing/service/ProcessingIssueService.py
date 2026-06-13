from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_processing.enums.ProcessingIssueSeverity import ProcessingIssueSeverity
from apps.kb.kb_processing.enums.ProcessingIssueStatus import ProcessingIssueStatus
from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from shared.utils.clock import utc_now_naive

logger = logging.getLogger(__name__)


class ProcessingIssueService:
    def __init__(self, issue_repository: ProcessingIssueRepository) -> None:
        self._issue_repository = issue_repository

    def open_issue(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_batch_id: str | None,
        training_item_id: str | None,
        job_id: str | None,
        module: str,
        stage: str,
        step: str | None,
        severity: ProcessingIssueSeverity | str,
        issue_code: str,
        issue_message: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        try:
            self._issue_repository.upsert_open(
                tenant_slug=tenant_slug,
                knowledge_base_id=knowledge_base_id,
                training_batch_id=training_batch_id,
                training_item_id=training_item_id,
                job_id=job_id,
                module=module,
                stage=stage,
                step=step,
                severity=str(severity),
                issue_code=issue_code,
                issue_message=issue_message,
                metadata_json=metadata_json,
            )
        except Exception:
            logger.warning(
                "Processing issue írás sikertelen (kb=%s code=%s)",
                knowledge_base_id,
                issue_code,
                exc_info=True,
            )

    def resolve_issue(self, issue_id: str) -> None:
        try:
            self._issue_repository.update_status(
                issue_id,
                status=ProcessingIssueStatus.RESOLVED.value,
                resolved_at=utc_now_naive(),
            )
        except Exception:
            logger.warning("Processing issue resolve sikertelen (id=%s)", issue_id, exc_info=True)

    def acknowledge_issue(self, issue_id: str) -> None:
        try:
            self._issue_repository.update_status(
                issue_id,
                status=ProcessingIssueStatus.ACKNOWLEDGED.value,
                resolved_at=None,
            )
        except Exception:
            logger.warning("Processing issue acknowledge sikertelen (id=%s)", issue_id, exc_info=True)

    def ignore_issue(self, issue_id: str) -> None:
        try:
            self._issue_repository.update_status(
                issue_id,
                status=ProcessingIssueStatus.IGNORED.value,
                resolved_at=utc_now_naive(),
            )
        except Exception:
            logger.warning("Processing issue ignore sikertelen (id=%s)", issue_id, exc_info=True)


__all__ = ["ProcessingIssueService"]
