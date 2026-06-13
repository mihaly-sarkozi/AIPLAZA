from __future__ import annotations

import os
from dataclasses import dataclass


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ExtractConfig:
    small_file_max_mb: int = 20
    large_file_max_mb: int = 200
    extra_large_file_max_mb: int = 1000
    max_extract_file_size_mb: int = 1000
    max_page_count: int = 500
    max_extract_duration_seconds: int = 600
    max_part_size: int = 50_000
    max_extract_parts: int = 50_000
    max_memory_usage_mb: int = 512
    ocr_min_text_chars: int = 50
    extract_batch_size: int = 50
    progress_update_interval_pages: int = 25
    ocr_language: str = "hun+eng+spa"
    keep_temp_files_on_error: bool = False

    @property
    def small_file_max_bytes(self) -> int:
        return self.small_file_max_mb * 1024 * 1024

    @property
    def large_file_max_bytes(self) -> int:
        return self.large_file_max_mb * 1024 * 1024

    @property
    def extra_large_file_max_bytes(self) -> int:
        return self.extra_large_file_max_mb * 1024 * 1024

    @property
    def max_extract_file_size_bytes(self) -> int:
        return self.max_extract_file_size_mb * 1024 * 1024

    # Backward-compatible alias
    @property
    def max_file_size_mb(self) -> int:
        return self.max_extract_file_size_mb

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_extract_file_size_bytes


DEFAULT_EXTRACT_CONFIG = ExtractConfig(
    small_file_max_mb=_env_int("SMALL_FILE_MAX_MB", 20),
    large_file_max_mb=_env_int("LARGE_FILE_MAX_MB", 200),
    extra_large_file_max_mb=_env_int("EXTRA_LARGE_FILE_MAX_MB", 1000),
    max_extract_file_size_mb=_env_int("MAX_EXTRACT_FILE_SIZE_MB", 1000),
    max_page_count=_env_int("MAX_EXTRACT_PAGE_COUNT", 500),
    max_extract_duration_seconds=_env_int("MAX_EXTRACT_DURATION_SECONDS", 600),
    max_part_size=_env_int("MAX_PART_SIZE", 50_000),
    max_extract_parts=_env_int("MAX_EXTRACT_PARTS", 50_000),
    max_memory_usage_mb=_env_int("MAX_MEMORY_USAGE", 512),
    extract_batch_size=_env_int("EXTRACT_BATCH_SIZE", 50),
    progress_update_interval_pages=_env_int("EXTRACT_PROGRESS_INTERVAL_PAGES", 25),
    keep_temp_files_on_error=_env_bool("KEEP_TEMP_FILES_ON_ERROR", False),
)


__all__ = ["DEFAULT_EXTRACT_CONFIG", "ExtractConfig"]
