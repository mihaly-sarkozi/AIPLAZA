from __future__ import annotations

# backend/apps/kb/kb_understanding/events/understanding_requested_handler.py
# Feladat: UNDERSTANDING_REQUESTED outbox job feldolgozása — tenant kontextus beállítás,
# Start + Pipeline futtatás. Idempotens: a lépések replace-szemantikájúak.
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any, Callable

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingNotFoundError import UnderstandingNotFoundError
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError

logger = logging.getLogger(__name__)


def make_understanding_requested_handler(services_provider: Callable[[], Any]):
    """Outbox handler factory.

    ``services_provider``: lazy ``UnderstandingServices`` gyár — a kompozíciós gyökér adja.
    """

    def _handle(payload: dict[str, Any]) -> None:
        training_item_id = str(payload.get("training_item_id") or "").strip()
        training_batch_id = str(payload.get("training_batch_id") or "").strip()
        knowledge_base_id = str(payload.get("knowledge_base_id") or "").strip()
        tenant_slug = payload.get("tenant_slug")
        created_by = payload.get("created_by")
        if not training_item_id or not training_batch_id or not knowledge_base_id:
            # Hibás payload — retry nem segít rajta, csak naplózunk.
            logger.error("kb.understanding_requested: érvénytelen payload: %r", payload)
            return

        from core.modules.tenant.context.tenant_context import current_tenant_schema

        token = current_tenant_schema.set(tenant_slug)
        try:
            services = services_provider()
            try:
                ctx = services.start_service.start(
                    training_item_id=training_item_id,
                    training_batch_id=training_batch_id,
                    knowledge_base_id=knowledge_base_id,
                    tenant_slug=tenant_slug,
                    created_by=created_by,
                )
            except UnderstandingNotFoundError:
                logger.error(
                    "kb.understanding_requested: item nem található (item=%s)", training_item_id
                )
                return
            except UnderstandingProcessingError as exc:
                if exc.code == UnderstandingErrorCode.JOB_ALREADY_RUNNING.value:
                    logger.info(
                        "kb.understanding_requested: már fut job az itemhez (item=%s)",
                        training_item_id,
                    )
                    return
                raise
            status = services.pipeline.run(ctx)
            logger.info(
                "kb.understanding_requested feldolgozva (item=%s job=%s status=%s)",
                training_item_id,
                ctx.job_id,
                status.value,
            )
        finally:
            current_tenant_schema.reset(token)

    return _handle


__all__ = ["make_understanding_requested_handler"]
