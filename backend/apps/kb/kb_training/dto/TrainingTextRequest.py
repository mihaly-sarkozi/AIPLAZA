from __future__ import annotations

# backend/apps/kb/kb_training/dto/TrainingTextRequest.py
# Feladat: Szöveges tanítás kérés sémája.
# Sárközi Mihály - 2026.06.07

from pydantic import BaseModel, Field


class TrainingTextRequest(BaseModel):
    """Szöveges tanítás — opcionális cím és tartalom."""
    title: str | None = None
    content: str = Field(..., min_length=1)


__all__ = ["TrainingTextRequest"]
