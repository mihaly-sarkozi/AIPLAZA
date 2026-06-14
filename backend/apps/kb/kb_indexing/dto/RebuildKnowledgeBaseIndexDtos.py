from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RebuildKnowledgeBaseIndexRequestDto:
    tenant_slug: str | None
    knowledge_base_id: str
    requested_by: int | None = None
    reason: str | None = None
    mode: str = "POINT_DELETE_AND_REINDEX"
    force: bool = False


@dataclass(frozen=True)
class RebuildKnowledgeBaseIndexResultDto:
    rebuild_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    training_items_total: int = 0
    training_items_reindexed: int = 0
    training_items_failed: int = 0
    points_deleted: int = 0
    points_reindexed: int = 0
    points_verified: int = 0


__all__ = ["RebuildKnowledgeBaseIndexRequestDto", "RebuildKnowledgeBaseIndexResultDto"]
