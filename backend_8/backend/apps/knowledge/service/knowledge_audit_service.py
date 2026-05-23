# backend/apps/knowledge/service/knowledge_audit_service.py
# Feladat: Knowledge ingest audit/event rekordok es megfigyelhetosegi esemenyek
# osszeallitasa. A KnowledgeFacade csak delegalja az audit felelosseget.

from __future__ import annotations

import logging
from typing import Any

from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.service.ports import IngestEventStorePort
from core.kernel.interface.observability import increment_metric, log_structured_event


class KnowledgeAuditService:
    def __init__(self, *, ingest_event_store: IngestEventStorePort) -> None:
        self._ingest_event_store = ingest_event_store

    def record_ingest_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        item_id: str | None = None,
        message: str | None = None,
        created_by: int | None = None,
        **details: Any,
    ) -> IngestEvent:
        event = IngestEvent(
            ingest_run_id=run_id,
            ingest_item_id=item_id,
            event_type=event_type,
            status=status,
            message=message,
            created_by=created_by,
            details=details,
        )
        created = self._ingest_event_store.create(event)
        if event_type == "ingest_run_created":
            increment_metric("ingest_jobs_total", 1.0, tags={"status": status})
            log_structured_event(
                "apps.knowledge.audit",
                "knowledge_training_started",
                level=logging.INFO,
                ingest_run_id=run_id,
                ingest_item_id=item_id,
                user_id=created_by,
                status=status,
            )
        if status in {"failed", "error"}:
            increment_metric("ingest_job_failures_total", 1.0, tags={"event_type": event_type})
        if "dead_letter" in str(event_type or "") or str(details.get("dead_letter_reason") or "").strip():
            increment_metric("ingest_dead_letters_total", 1.0, tags={"event_type": event_type})
        log_structured_event(
            "apps.knowledge.ingest",
            event_type,
            level=logging.INFO if status not in {"failed", "error"} else logging.ERROR,
            event_type=event_type,
            status=status,
            ingest_run_id=run_id,
            ingest_item_id=item_id,
            details=details,
            message=message,
        )
        return created


__all__ = ["KnowledgeAuditService"]
