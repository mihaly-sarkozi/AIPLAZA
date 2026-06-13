from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryJobContext:
    job_id: str
    understanding_job_id: str
    training_item_id: str
    training_batch_id: str
    knowledge_base_id: str
    tenant_slug: str | None
    created_by: int | None
    source_type: str
    title: str
    language_code: str = "unknown"
    language_confidence: float = 0.0


__all__ = ["DiscoveryJobContext"]
