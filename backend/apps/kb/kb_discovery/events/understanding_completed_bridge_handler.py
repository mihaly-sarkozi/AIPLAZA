from __future__ import annotations

import logging
from typing import Any

from apps.kb.kb_discovery.events.discovery_requested_event import add_discovery_requested_event
from apps.kb.shared.events import UNDERSTANDING_COMPLETED

logger = logging.getLogger(__name__)


def make_understanding_completed_bridge_handler(understanding_job_reader):
    def _handle(payload: dict[str, Any]) -> None:
        status = str(payload.get("status") or "")
        if status not in {"ready_for_discovery", "partial"}:
            logger.info(
                "understanding_completed bridge: skip discovery (status=%s item=%s)",
                status,
                payload.get("training_item_id"),
            )
            return
        understanding_job_id = str(payload.get("understanding_job_id") or payload.get("job_id") or "")
        training_item_id = str(payload.get("training_item_id") or "")
        knowledge_base_id = str(payload.get("knowledge_base_id") or "")
        tenant_slug = payload.get("tenant_slug")
        created_by = payload.get("created_by")
        training_batch_id = str(payload.get("training_batch_id") or "")
        if not training_batch_id and understanding_job_id:
            job = understanding_job_reader.get_job(understanding_job_id)
            if job:
                training_batch_id = str(job.get("training_batch_id") or "")
                created_by = created_by if created_by is not None else job.get("created_by")
        if not training_batch_id:
            logger.error("understanding_completed bridge: hiányzó training_batch_id (job=%s)", understanding_job_id)
            return
        add_discovery_requested_event(
            tenant_slug=tenant_slug,
            knowledge_base_id=knowledge_base_id,
            training_batch_id=training_batch_id,
            training_item_id=training_item_id,
            understanding_job_id=understanding_job_id,
            created_by=created_by,
        )
        logger.info(
            "%s bridge → discovery_requested (item=%s und_job=%s)",
            UNDERSTANDING_COMPLETED,
            training_item_id,
            understanding_job_id,
        )

    return _handle


__all__ = ["make_understanding_completed_bridge_handler"]
