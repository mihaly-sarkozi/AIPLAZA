# backend/apps/kb/kb_ingest/events/understanding_requested_event.py
# Feladat: Tanítás után understanding kérés esemény írása a platform job queue-ba.
# A payload csak azonosítókat tartalmaz; a worker a DB-ből tölti az adatokat.
# Sárközi Mihály - 2026.06.07

from __future__ import annotations

from core.kernel.jobs import enqueue_job

from apps.kb.kb_ingest.config import MetricsConf
from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.enums.TrainingMetric import TrainingMetric
from apps.kb.kb_ingest.errors.TrainingProcessingError import TrainingProcessingError
from apps.kb.shared.events import UNDERSTANDING_REQUESTED


def add_understanding_requested_event(
    *,
    tenant_slug: str | None,
    training_batch_id: str,
    training_item_id: str,
    knowledge_base_id: str,
    created_by: int | None,
    input_type: str = "text",
) -> None:
    """Understanding feldolgozás ütemezése platform outbox-on keresztül."""
    batch_id = str(training_batch_id or "").strip()
    item_id = str(training_item_id or "").strip()
    kb_id = str(knowledge_base_id or "").strip()
    if not batch_id or not item_id or not kb_id:
        raise TrainingProcessingError(TrainingErrorCode.INVALID_EVENT_PAYLOAD)
    enqueue_job(
        UNDERSTANDING_REQUESTED,
        {
            "tenant_slug": tenant_slug,
            "training_batch_id": batch_id,
            "training_item_id": item_id,
            "knowledge_base_id": kb_id,
            "created_by": created_by,
        },
        idempotency_key=f"{UNDERSTANDING_REQUESTED}:{tenant_slug or '_'}:{item_id}",
    )
    MetricsConf.increment(TrainingMetric.UNDERSTANDING_REQUESTED, input_type=input_type)


__all__ = ["add_understanding_requested_event"]
