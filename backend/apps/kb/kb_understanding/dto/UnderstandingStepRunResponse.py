from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingStepRunResponse.py
# Feladat: Egy pipeline-lépés futásának HTTP válaszmodellje.
# Sárközi Mihály - 2026.06.11

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UnderstandingStepRunResponse(BaseModel):
    step: str
    status: str
    duration_ms: int = 0
    input_summary: dict[str, Any] = Field(default_factory=dict)
    output_summary: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None


__all__ = ["UnderstandingStepRunResponse"]
