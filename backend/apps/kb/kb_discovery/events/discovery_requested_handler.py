from __future__ import annotations

import logging
from typing import Any, Callable

from apps.kb.kb_discovery.enums.DiscoveryErrorCode import DiscoveryErrorCode
from apps.kb.kb_discovery.errors.DiscoveryProcessingError import DiscoveryProcessingError

logger = logging.getLogger(__name__)


def make_discovery_requested_handler(services_provider: Callable[[], Any]):
    def _handle(payload: dict[str, Any]) -> None:
        training_item_id = str(payload.get("training_item_id") or "").strip()
        training_batch_id = str(payload.get("training_batch_id") or "").strip()
        knowledge_base_id = str(payload.get("knowledge_base_id") or "").strip()
        understanding_job_id = str(payload.get("understanding_job_id") or "").strip()
        tenant_slug = payload.get("tenant_slug")
        created_by = payload.get("created_by")
        if not training_item_id or not training_batch_id or not knowledge_base_id or not understanding_job_id:
            logger.error("kb.discovery_requested: érvénytelen payload: %r", payload)
            return

        from core.modules.tenant.context.tenant_context import current_tenant_schema

        token = current_tenant_schema.set(tenant_slug)
        try:
            services = services_provider()
            try:
                ctx, chunks = services.start_service.start(
                    understanding_job_id=understanding_job_id,
                    training_item_id=training_item_id,
                    training_batch_id=training_batch_id,
                    knowledge_base_id=knowledge_base_id,
                    tenant_slug=tenant_slug,
                    created_by=created_by,
                )
            except DiscoveryProcessingError as exc:
                if exc.code == DiscoveryErrorCode.JOB_ALREADY_RUNNING.value:
                    logger.info(
                        "kb.discovery_requested: már fut discovery job (item=%s)",
                        training_item_id,
                    )
                    return
                raise
            status = services.pipeline.run(ctx, chunks)
            logger.info(
                "kb.discovery_requested feldolgozva (item=%s job=%s status=%s)",
                training_item_id,
                ctx.job_id,
                status.value,
            )
        finally:
            current_tenant_schema.reset(token)

    return _handle


__all__ = ["make_discovery_requested_handler"]
