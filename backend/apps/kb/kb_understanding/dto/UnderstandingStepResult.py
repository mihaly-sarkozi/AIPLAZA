from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingStepResult.py
# Feladat: Egy pipeline-lépés futásának eredménye (trace-hez és hibakezeléshez).
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.enums.UnderstandingStep import UnderstandingStep


@dataclass(frozen=True)
class UnderstandingStepResult:
    step: UnderstandingStep
    # completed | failed | skipped
    status: str
    duration_ms: int = 0
    input_summary: dict[str, Any] = field(default_factory=dict)
    output_summary: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


__all__ = ["UnderstandingStepResult"]
