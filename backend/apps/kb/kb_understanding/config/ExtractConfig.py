from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


@dataclass(frozen=True)
class ExtractConfig:
    max_file_size_mb: int = 200
    max_page_count: int = 500
    max_extract_duration_seconds: int = 600
    max_part_size: int = 50_000
    max_memory_usage_mb: int = 512
    ocr_min_text_chars: int = 50
    extract_batch_size: int = 50
    ocr_language: str = "hun+eng+deu"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


DEFAULT_EXTRACT_CONFIG = ExtractConfig(
    max_file_size_mb=_env_int("MAX_FILE_SIZE_MB", 200),
    max_page_count=_env_int("MAX_PAGE_COUNT", 500),
    max_extract_duration_seconds=_env_int("MAX_EXTRACT_DURATION_SECONDS", 600),
    max_part_size=_env_int("MAX_PART_SIZE", 50_000),
    max_memory_usage_mb=_env_int("MAX_MEMORY_USAGE", 512),
)


__all__ = ["DEFAULT_EXTRACT_CONFIG", "ExtractConfig"]
