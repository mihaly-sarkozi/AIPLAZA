from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/TrainingTextRequest.py
# Feladat: Szöveges tanítás kérés sémája.
# Sárközi Mihály - 2026.06.07

from pydantic import BaseModel, Field

from apps.kb.kb_ingest.config.TrainingConf import DEFAULT_TRAINING_CONFIG


class TrainingTextRequest(BaseModel):
    """HTTP kérés a szöveges tanítás beküldésére (`TrainingTextResponse` párja)."""
    title: str | None = Field(default=None, max_length=DEFAULT_TRAINING_CONFIG.max_title_length)
    content: str = Field(..., min_length=1, max_length=DEFAULT_TRAINING_CONFIG.max_text_chars)


__all__ = ["TrainingTextRequest"]
