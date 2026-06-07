from __future__ import annotations

# backend/apps/kb/jobs/process_training_understanding.py
# Feladat: Outbox worker belépőpont — modulhatárokon átívelő wiring (training DB → understanding).
# Sárközi Mihály - 2026.06.07

import logging

from apps.kb.kb_training.bootstrap.service_keys import KB_TRAINING_REPOSITORY
from apps.kb.kb_training.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_training.enums.TrainingItemStatus import TrainingItemStatus
from apps.kb.kb_training.errors.TrainingProcessingError import TrainingProcessingError
from apps.kb.kb_understanding.service.ProcessTrainingUnderstandingService import (
    ProcessTrainingUnderstandingService,
)
from core.kernel.http.app_dependencies import get_module_repository
from core.modules.tenant.context.tenant_context import run_with_tenant_schema

logger = logging.getLogger(__name__)


def process_training_understanding_sync(
    *,
    tenant_slug: str | None,
    training_item_id: str,
    created_by: int | None,
) -> None:
    """Worker: training_item_id alapján DB-ből olvas, majd understanding service."""

    def _run() -> None:
        item_id = str(training_item_id or "").strip()
        if not item_id:
            raise TrainingProcessingError(TrainingErrorCode.INVALID_EVENT_PAYLOAD)
        repository = get_module_repository(KB_TRAINING_REPOSITORY)
        item = repository.get_item(item_id)
        if item is None:
            raise TrainingProcessingError(TrainingErrorCode.ITEM_NOT_FOUND, item_id=item_id)
        if item.status != TrainingItemStatus.ACCEPTED.value:
            logger.warning(
                "understanding_skipped_non_accepted_item",
                extra={"training_item_id": item_id, "status": item.status},
            )
            return
        if not item.raw_ref:
            raise TrainingProcessingError(TrainingErrorCode.RAW_REF_REQUIRED, item_id=item_id)
        ProcessTrainingUnderstandingService().execute(
            tenant=str(tenant_slug or ""),
            training_item_id=item.id,
            training_batch_id=item.training_batch_id,
            knowledge_base_id=item.knowledge_base_id,
            raw_ref=item.raw_ref,
            input_type=item.input_type,
            created_by=created_by,
        )

    run_with_tenant_schema(tenant_slug, _run)


__all__ = ["process_training_understanding_sync"]
