from __future__ import annotations

import time
from typing import Callable

from apps.kb.kb_understanding.config.ExtractConfig import ExtractConfig
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError


class ExtractLimits:
    def __init__(self, config: ExtractConfig) -> None:
        self._config = config
        self._started = time.monotonic()
        self.timed_out = False

    def check_file_size_bytes(self, size_bytes: int) -> None:
        if size_bytes > self._config.max_extract_file_size_bytes:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.FILE_TOO_LARGE,
                size_bytes=size_bytes,
                max_bytes=self._config.max_extract_file_size_bytes,
            )

    def check_file_size(self, data: bytes) -> None:
        self.check_file_size_bytes(len(data))

    def check_page_count(self, page_count: int) -> None:
        if page_count > self._config.max_page_count:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.TOO_MANY_PAGES,
                page_count=page_count,
                max_pages=self._config.max_page_count,
            )

    def check_part_count(self, part_count: int) -> None:
        if part_count > self._config.max_extract_parts:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.TOO_MANY_PARTS,
                part_count=part_count,
                max_parts=self._config.max_extract_parts,
            )

    def check_duration(self) -> None:
        elapsed = time.monotonic() - self._started
        if elapsed > self._config.max_extract_duration_seconds:
            self.timed_out = True
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.EXTRACTION_TIMEOUT,
                elapsed_seconds=int(elapsed),
            )

    def check_part_size(self, text: str) -> None:
        if len(text) > self._config.max_part_size:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.PART_TOO_LARGE,
                part_size=len(text),
                max_size=self._config.max_part_size,
            )


def finalize_extract_status(
    *,
    parts,
    failed_pages: int,
    warnings: list[str],
    timed_out: bool = False,
    counters=None,
) -> str:
    from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
    from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus

    def _usable(part) -> bool:
        return (
            part.part_type
            in {
                ExtractPartType.TEXT.value,
                ExtractPartType.TABLE.value,
                ExtractPartType.OCR_TEXT.value,
            }
            and (part.text or "").strip()
            and part.status == "completed"
        )

    if counters is not None:
        usable = any(
            getattr(counters, field, 0) > 0
            for field in ("text_parts", "table_parts", "ocr_text_parts")
        )
    else:
        usable = any(_usable(part) for part in parts)

    if not usable:
        return ExtractStatus.FAILED.value
    if timed_out:
        return ExtractStatus.PARTIAL_TIMEOUT.value
    if failed_pages > 0 or warnings:
        return ExtractStatus.PARTIAL.value
    return ExtractStatus.COMPLETED.value


__all__ = ["ExtractLimits", "finalize_extract_status"]
