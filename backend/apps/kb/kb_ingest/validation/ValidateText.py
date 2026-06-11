from __future__ import annotations

# backend/apps/kb/kb_ingest/validation/ValidateText.py
# Feladat: Tanítási szöveg normalizálása és ellenőrzése (üres, hossz).
# Sárközi Mihály - 2026.06.07

import unicodedata

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.config.TrainingConf import DEFAULT_TRAINING_CONFIG, TrainingConfig
from apps.kb.kb_ingest.validation.TrainingValidationError import TrainingValidationError


def validate_text(
    value: str | None,
    *,
    config: TrainingConfig | None = None,
) -> str:
    """Normalizálja és ellenőrzi a tanítási szöveget."""
    cfg = config or DEFAULT_TRAINING_CONFIG
    text = str(value or "")
    text = text.removeprefix("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = unicodedata.normalize("NFC", text)
    if not normalized.strip():
        raise TrainingValidationError(TrainingErrorCode.TEXT_REQUIRED)
    if len(normalized) > cfg.max_text_chars:
        raise TrainingValidationError(
            TrainingErrorCode.TEXT_TOO_LONG,
            max_chars=cfg.max_text_chars,
        )
    return normalized


__all__ = ["validate_text"]
