from __future__ import annotations

from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.ingest_progress_service import IngestProgressService


class ProgressCompatibilityMixin:
    @staticmethod
    def _compute_progress_percent(processed_parts: int | None, total_parts: int | None) -> int | None:
        return IngestProgressService.compute_progress_percent(processed_parts, total_parts)

    @staticmethod
    def _estimate_file_character_count_from_size(size_bytes: int | None) -> int:
        return IngestProgressService.estimate_file_character_count_from_size(size_bytes)

    @staticmethod
    def _format_size_label(size_bytes: int | None) -> str:
        return IngestProgressService.format_size_label(size_bytes)

    @staticmethod
    def _build_processing_module(**kwargs: Any) -> dict[str, Any]:
        return IngestProgressService.build_processing_module(**kwargs)

    @staticmethod
    def _build_document_progress(**kwargs: Any) -> dict[str, Any]:
        return IngestProgressService.build_document_progress(**kwargs)

    @staticmethod
    def _compute_item_progress_percent(item: IngestItem) -> int | None:
        return IngestProgressService.compute_item_progress_percent(item)

    def _update_item_processing_summary(self, item: IngestItem, **kwargs: Any) -> IngestItem:
        return self._ingest_progress_service.update_item_processing_summary(item, **kwargs)


__all__ = ["ProgressCompatibilityMixin"]
