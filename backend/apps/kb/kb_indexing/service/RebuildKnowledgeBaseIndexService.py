from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RebuildKnowledgeBaseIndexService:
    """Skeleton: teljes KB Qdrant collection rebuild Postgres source of truth alapján."""

    def rebuild(self, *, tenant_slug: str | None, knowledge_base_id: str) -> str:
        logger.info(
            "RebuildKnowledgeBaseIndexService.rebuild skeleton (kb=%s tenant=%s)",
            knowledge_base_id,
            tenant_slug,
        )
        raise NotImplementedError("RebuildKnowledgeBaseIndexService not implemented yet")


__all__ = ["RebuildKnowledgeBaseIndexService"]
