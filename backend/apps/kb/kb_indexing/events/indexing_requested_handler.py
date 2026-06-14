from __future__ import annotations

import logging
from typing import Any, Callable

from apps.kb.kb_indexing.enums.IndexingErrorCode import IndexingErrorCode
from apps.kb.kb_indexing.enums.IndexingStatus import IndexingStatus
from apps.kb.kb_indexing.errors.IndexingProcessingError import IndexingProcessingError

logger = logging.getLogger(__name__)


def make_indexing_requested_handler(services_provider: Callable[[], Any]):
    def _handle(payload: dict[str, Any]) -> None:
        training_item_id = str(payload.get("training_item_id") or "").strip()
        knowledge_base_id = str(payload.get("knowledge_base_id") or "").strip()
        understanding_job_id = str(payload.get("understanding_job_id") or "").strip()
        discovery_job_id = str(payload.get("discovery_job_id") or "").strip()
        embedding_job_id = str(payload.get("embedding_job_id") or "").strip()
        tenant_slug = payload.get("tenant_slug")
        created_by = payload.get("created_by")
        if (
            not training_item_id
            or not knowledge_base_id
            or not understanding_job_id
            or not discovery_job_id
            or not embedding_job_id
        ):
            logger.error("kb.indexing_requested: érvénytelen payload: %r", payload)
            return

        from core.modules.tenant.context.tenant_context import current_tenant_schema

        token = current_tenant_schema.set(tenant_slug)
        try:
            services = services_provider()
            try:
                status = services.start_service.start(
                    tenant_slug=tenant_slug,
                    knowledge_base_id=knowledge_base_id,
                    training_item_id=training_item_id,
                    understanding_job_id=understanding_job_id,
                    discovery_job_id=discovery_job_id,
                    embedding_job_id=embedding_job_id,
                    created_by=created_by,
                )
            except IndexingProcessingError as exc:
                if exc.code == IndexingErrorCode.JOB_ALREADY_RUNNING.value:
                    logger.info(
                        "kb.indexing_requested: már fut indexing job (embedding=%s)",
                        embedding_job_id,
                    )
                    return
                logger.exception("kb.indexing_requested: váratlan indexing hiba (code=%s)", exc.code)
                raise
            logger.info(
                "kb.indexing_requested feldolgozva (item=%s embedding=%s status=%s)",
                training_item_id,
                embedding_job_id,
                status.value,
            )
        finally:
            current_tenant_schema.reset(token)

    return _handle


__all__ = ["make_indexing_requested_handler"]
