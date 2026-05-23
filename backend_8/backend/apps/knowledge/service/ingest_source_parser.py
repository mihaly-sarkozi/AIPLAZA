from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import time
from typing import Any

from apps.knowledge.domain.source import Source
from apps.knowledge.errors import KnowledgeValidationError
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    observe_metric as observe_platform_metric,
)
from shared.documents import ExtractedDocument, ExtractedParagraph, extract_document_from_upload


class IngestSourceParser:
    def __init__(
        self,
        *,
        object_storage: Any,
        url_fetch_service: Any,
        normalize_parser_text: Callable[[str | None], str],
        estimate_file_character_count_from_size: Callable[[int | None], int],
    ) -> None:
        self._object_storage = object_storage
        self._url_fetch_service = url_fetch_service
        self._normalize_parser_text = normalize_parser_text
        self._estimate_file_character_count_from_size = estimate_file_character_count_from_size

    def extract_document(
        self,
        source: Source,
        *,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ExtractedDocument:
        if source.source_type == "text":
            return self._extract_text_source(source)
        if source.source_type == "file":
            return self._extract_file_source(source, progress_callback=progress_callback)
        if source.source_type == "url":
            return self._extract_url_source(source)
        fallback_text = self._normalize_parser_text(source.raw_content)
        return ExtractedDocument(
            text_content=fallback_text,
            paragraphs=[ExtractedParagraph(text=fallback_text)] if fallback_text else [],
            metadata={"source_type": source.source_type, "extraction_engine": "fallback_text_v1"},
        )

    def _extract_text_source(self, source: Source) -> ExtractedDocument:
        text = self._normalize_parser_text(source.raw_content)
        return ExtractedDocument(
            text_content=text,
            paragraphs=[ExtractedParagraph(text=text)] if text else [],
            metadata={"source_type": source.source_type, "extraction_engine": "manual_text_v1"},
        )

    def _extract_url_source(self, source: Source) -> ExtractedDocument:
        url = str(source.metadata.get("origin_url") or "")
        if not url:
            raise KnowledgeValidationError("A hivatkozás forráshoz hiányzik az URL.")
        return self._url_fetch_service.fetch_document(url, timeout=20)

    def _extract_file_source(
        self,
        source: Source,
        *,
        progress_callback: Callable[[str, dict[str, Any]], None] | None,
    ) -> ExtractedDocument:
        parse_started = time.perf_counter()
        bucket_name = str(source.metadata.get("bucket_name") or "")
        object_key = str(source.metadata.get("object_key") or "")
        filename = str(source.file_ref or source.title or "upload.txt")
        size_bytes = int(source.metadata.get("size_bytes") or 0)
        estimated_char_count = int(
            source.metadata.get("estimated_char_count")
            or self._estimate_file_character_count_from_size(size_bytes)
        )
        if not bucket_name or not object_key:
            raise KnowledgeValidationError("A fájlforráshoz hiányzik az object storage referencia.")
        self._emit(progress_callback, "file_character_count_started", filename, size_bytes, estimated_char_count, 0)
        stored = self._object_storage.get_bytes(key=object_key, bucket=bucket_name)
        loaded_size_bytes = len(stored.body)
        self._emit(
            progress_callback,
            "file_bytes_loaded",
            filename,
            size_bytes or loaded_size_bytes,
            estimated_char_count,
            loaded_size_bytes,
        )
        try:
            extracted = extract_document_from_upload(filename, stored.body)
        except Exception:
            increment_platform_metric("file_parse_failures_total", 1.0, tags={"source_type": "file"})
            raise
        finally:
            observe_platform_metric(
                "file_parse_duration_seconds",
                time.perf_counter() - parse_started,
                unit="seconds",
                tags={"source_type": "file"},
            )
        normalized_text = self._normalize_parser_text(extracted.text_content)
        normalized_paragraphs = [
            replace(paragraph, text=self._normalize_parser_text(paragraph.text))
            for paragraph in extracted.paragraphs
            if self._normalize_parser_text(paragraph.text)
        ]
        if not normalized_paragraphs and normalized_text:
            normalized_paragraphs = [ExtractedParagraph(text=normalized_text)]
        if progress_callback is not None:
            progress_callback(
                "file_character_count_completed",
                {
                    "filename": filename,
                    "size_bytes": size_bytes or loaded_size_bytes,
                    "estimated_char_count": estimated_char_count,
                    "char_count": len(normalized_text),
                    "paragraph_count": len(normalized_paragraphs),
                },
            )
        return ExtractedDocument(
            text_content=normalized_text,
            paragraphs=normalized_paragraphs,
            metadata={**dict(extracted.metadata or {}), "source_type": source.source_type, "filename": filename},
        )

    @staticmethod
    def _emit(
        progress_callback: Callable[[str, dict[str, Any]], None] | None,
        stage: str,
        filename: str,
        size_bytes: int,
        estimated_char_count: int,
        processed_bytes: int,
    ) -> None:
        if progress_callback is None:
            return
        progress_callback(
            stage,
            {
                "filename": filename,
                "size_bytes": size_bytes,
                "estimated_char_count": estimated_char_count,
                "processed_bytes": processed_bytes,
            },
        )


__all__ = ["IngestSourceParser"]
