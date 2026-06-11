from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/UnderstandingJobRequest.py
# Feladat: Megértési job indítás / újrafuttatás HTTP kérése.
# Sárközi Mihály - 2026.06.11

from pydantic import BaseModel


class UnderstandingJobRequest(BaseModel):
    """Retry kérés — force=True lezárt (nem RETRYABLE/FAILED) jobot is újrafuttat."""

    force: bool = False


__all__ = ["UnderstandingJobRequest"]
