from __future__ import annotations

# backend/apps/kb/kb_ingest/config/ReadingConfig.py
# Feladat: Fájl beolvasási/feltöltési beállítások és alapértelmezések.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field

from shared.utils.idempotency import DEFAULT_IDEMPOTENCY_PIPELINE_VERSION


@dataclass(frozen=True)
class ReadingConfig:
    """Beolvasás beállítások gyűjteménye."""
    pipeline_version: str = DEFAULT_IDEMPOTENCY_PIPELINE_VERSION
    max_title_length: int = 200
    max_files_per_batch: int = 20
    max_file_bytes: int = 25 * 1024 * 1024
    max_total_upload_bytes: int = 250 * 1024 * 1024
    allowed_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({".txt", ".pdf", ".docx"}),
    )
    allowed_url_schemes: frozenset[str] = field(
        default_factory=lambda: frozenset({"http", "https"}),
    )
    max_url_length: int = 2048


DEFAULT_READING_CONFIG = ReadingConfig()

__all__ = ["DEFAULT_READING_CONFIG", "ReadingConfig"]
