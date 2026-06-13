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


def _env_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return raw.strip()


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
    keep_temp_files_on_error: bool = False
    ocr_enabled: bool = True
    ocr_languages: str = "hun+eng+spa"
    ocr_min_confidence: float = 0.50
    ocr_deduplicate: bool = True
    ocr_run_on_pdf_images: bool = True
    ocr_run_on_docx_images: bool = True
    ocr_run_on_low_text_pdf_pages: bool = True
    ocr_max_image_pixels: int = 20_000_000
    ocr_timeout_seconds: int = 120

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

    @property
    def max_file_size_mb(self) -> int:
        return self.max_extract_file_size_mb

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_extract_file_size_bytes

    # Backward-compatible alias
    @property
    def ocr_language(self) -> str:
        return self.ocr_languages


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
    ocr_enabled=_env_bool("OCR_ENABLED", True),
    ocr_languages=_env_str("OCR_LANGUAGES", "hun+eng+spa"),
    ocr_min_confidence=float(os.getenv("OCR_MIN_CONFIDENCE", "0.50") or "0.50"),
    ocr_deduplicate=_env_bool("OCR_DEDUPLICATE", True),
    ocr_run_on_pdf_images=_env_bool("OCR_RUN_ON_PDF_IMAGES", True),
    ocr_run_on_docx_images=_env_bool("OCR_RUN_ON_DOCX_IMAGES", True),
    ocr_run_on_low_text_pdf_pages=_env_bool("OCR_RUN_ON_LOW_TEXT_PDF_PAGES", True),
    ocr_max_image_pixels=_env_int("OCR_MAX_IMAGE_PIXELS", 20_000_000),
    ocr_timeout_seconds=_env_int("OCR_TIMEOUT_SECONDS", 120),
)


__all__ = ["DEFAULT_EXTRACT_CONFIG", "ExtractConfig"]
