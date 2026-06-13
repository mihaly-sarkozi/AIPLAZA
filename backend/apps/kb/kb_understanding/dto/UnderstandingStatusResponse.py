from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingStatusResponse.py
# Feladat: Egy ingest item megértési állapotának teljes HTTP válasza.
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel, Field

from apps.kb.kb_understanding.dto.UnderstandingJobResponse import UnderstandingJobResponse
from apps.kb.kb_understanding.dto.UnderstandingStepRunResponse import UnderstandingStepRunResponse


class UnderstandingStatusResponse(BaseModel):
    job: UnderstandingJobResponse | None = None
    steps: list[UnderstandingStepRunResponse] = Field(default_factory=list)
    chunk_count: int = 0


__all__ = ["UnderstandingStatusResponse"]
