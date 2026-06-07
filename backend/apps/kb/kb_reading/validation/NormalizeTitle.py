from __future__ import annotations

# backend/apps/kb/kb_reading/validation/title.py
# Feladat: Cím normalizálás és ellenőrzés.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_reading.support.ReadingConfig import DEFAULT_READING_CONFIG, ReadingConfig


def normalize_title(value: str | None, *, fallback: str = "Untitled", config: ReadingConfig | None = None) -> str:
    """Normalizálja és ellenőrzi a címet."""
    cfg = config or DEFAULT_READING_CONFIG
    normalized = str(value or "").strip()
    title = normalized or str(fallback or "").strip() or "Untitled"
    return title[: cfg.max_title_length]


__all__ = ["normalize_title"]
