from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.part_builder import build_text_part, summarize_parts


class ManualTextExtractorAdapter:
    name = "plain_text"
    version = "2.0"

    def __init__(self, *, config: ExtractConfig | None = None) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        limits = ExtractLimits(self._config)
        limits.check_file_size(data)
        text = data.decode("utf-8", errors="replace")
        limits.check_part_size(text)
        part = build_text_part(
            page_number=1,
            part_index=0,
            text=text,
            metadata={"source": "plain_text"},
        )
        parts = [part] if text.strip() else []
        status = finalize_extract_status(parts=parts, failed_pages=0, warnings=[])
        return ExtractResult(
            total_pages=1,
            parts=parts,
            total_chars=summarize_parts(parts),
            warnings=[],
            status=status,
            extractor_name=self.name,
            extractor_version=self.version,
            processed_pages=1,
            failed_pages=0,
            source_mime=mime_type or "text/plain",
        )


__all__ = ["ManualTextExtractorAdapter"]
