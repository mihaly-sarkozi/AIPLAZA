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

    def check_file_size(self, data: bytes) -> None:
        if len(data) > self._config.max_file_size_bytes:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.FILE_TOO_LARGE,
                size_bytes=len(data),
                max_bytes=self._config.max_file_size_bytes,
            )

    def check_page_count(self, page_count: int) -> None:
        if page_count > self._config.max_page_count:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.TOO_MANY_PAGES,
                page_count=page_count,
                max_pages=self._config.max_page_count,
            )

    def check_duration(self) -> None:
        elapsed = time.monotonic() - self._started
        if elapsed > self._config.max_extract_duration_seconds:
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


def finalize_extract_status(*, parts, failed_pages: int, warnings: list[str]) -> str:
    from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
    from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus

    usable = any(
        part.part_type in {
            ExtractPartType.TEXT.value,
            ExtractPartType.TABLE.value,
            ExtractPartType.OCR_TEXT.value,
        }
        and (part.text or "").strip()
        for part in parts
    )
    if not usable:
        return ExtractStatus.FAILED.value
    if failed_pages > 0 or warnings:
        return ExtractStatus.PARTIAL.value
    return ExtractStatus.COMPLETED.value


__all__ = ["ExtractLimits", "finalize_extract_status"]
