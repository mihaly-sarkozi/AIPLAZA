from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReindexTrainingItemRequestDto:
    tenant_slug: str | None
    knowledge_base_id: str
    training_item_id: str
    requested_by: int | None = None
    reason: str | None = None
    force: bool = False
    embedding_job_id: str | None = None


@dataclass(frozen=True)
class ReindexTrainingItemResultDto:
    indexing_job_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    points_deleted: int = 0
    points_indexed: int = 0
    points_verified: int = 0
    verification_id: str | None = None
    embedding_job_id: str | None = None


__all__ = ["ReindexTrainingItemRequestDto", "ReindexTrainingItemResultDto"]
