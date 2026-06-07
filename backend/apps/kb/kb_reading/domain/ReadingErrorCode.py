from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadingErrorCode.py
# Feladat: Hibakódok a beolvasás során.
# Sárközi Mihály - 2026.06.07

from enum import Enum


class ReadingErrorCode(str, Enum):
    """Hibakódok a beolvasás során."""
    DUPLICATE_CONTENT = "duplicate_content"
    INVALID_URL = "invalid_url"
    FETCH_TIMEOUT = "fetch_timeout"
    FETCH_FAILED = "fetch_failed"
    STORAGE_ERROR = "storage_error"
    QUOTA_EXCEEDED = "quota_exceeded"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    INTERNAL_ERROR = "internal_error"


__all__ = ["ReadingErrorCode"]
