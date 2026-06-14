from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class ReindexTrainingItemService:
    """Skeleton: training item Qdrant pointjainak újraindexelése."""

    def reindex(
        self,
        *,
        tenant_slug: str | None,
        knowledge_base_id: str,
        training_item_id: str,
        embedding_job_id: str,
    ) -> str:
        logger.info(
            "ReindexTrainingItemService.reindex skeleton (kb=%s item=%s embedding=%s)",
            knowledge_base_id,
            training_item_id,
            embedding_job_id,
        )
        raise NotImplementedError("ReindexTrainingItemService not implemented yet")


__all__ = ["ReindexTrainingItemService"]
