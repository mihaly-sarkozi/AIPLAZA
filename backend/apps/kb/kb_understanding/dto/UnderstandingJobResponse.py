from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingJobResponse.py
# Feladat: Megértési job HTTP válaszmodellje.
# Sárközi Mihály - 2026.06.11

from datetime import datetime

from pydantic import BaseModel


class UnderstandingJobResponse(BaseModel):
    id: str
    training_item_id: str
    training_batch_id: str
    knowledge_base_id: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    retry_count: int = 0
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


__all__ = ["UnderstandingJobResponse"]
