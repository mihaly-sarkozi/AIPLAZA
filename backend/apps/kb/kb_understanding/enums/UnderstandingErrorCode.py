from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/UnderstandingErrorCode.py
# Feladat: Megértési modul gépi hibakódjai (UI fordítás a kódból).
# Sárközi Mihály - 2026.06.11

from enum import Enum


class UnderstandingErrorCode(str, Enum):
    ITEM_NOT_FOUND = "item_not_found"
    JOB_NOT_FOUND = "job_not_found"
    JOB_ALREADY_RUNNING = "job_already_running"
    JOB_NOT_RETRYABLE = "job_not_retryable"
    RAW_REF_MISSING = "raw_ref_missing"
    STORAGE_ERROR = "storage_error"
    UNSUPPORTED_CONTENT_TYPE = "unsupported_content_type"
    EXTRACTION_FAILED = "extraction_failed"
    DOCX_PART_PARSE_ERROR = "docx_part_parse_error"
    FILE_TOO_LARGE = "file_too_large"
    TOO_MANY_PAGES = "too_many_pages"
    EXTRACTION_TIMEOUT = "extraction_timeout"
    PART_TOO_LARGE = "part_too_large"
    OCR_UNAVAILABLE = "ocr_unavailable"
    OCR_ENGINE_UNAVAILABLE = "ocr_engine_unavailable"
    OCR_LANGUAGE_PACK_MISSING = "ocr_language_pack_missing"
    OCR_FAILED = "ocr_failed"
    FILE_REJECTED = "file_rejected"
    TOO_MANY_PARTS = "too_many_parts"
    EMPTY_CONTENT = "empty_content"
    NORMALIZATION_FAILED = "normalization_failed"
    CHUNKING_FAILED = "chunking_failed"
    NO_CHUNKS = "no_chunks"
    VALIDATION_FAILED = "validation_failed"
    INVALID_EVENT_PAYLOAD = "invalid_event_payload"
    INTERNAL_ERROR = "internal_error"


__all__ = ["UnderstandingErrorCode"]
