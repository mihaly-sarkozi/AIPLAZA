from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.extract.extract_context import ExtractContext
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.part_builder import build_text_part, summarize_parts


class ManualTextExtractorAdapter:
    name = "plain_text"
    version = "2.1"

    def __init__(self, *, config: ExtractConfig | None = None) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        return self.extract_from_bytes(data, mime_type=mime_type)

    def extract_from_path(
        self,
        path: str,
        *,
        mime_type: str | None = None,
        extract_ctx: ExtractContext | None = None,
    ) -> ExtractResult:
        limits = extract_ctx.limits if extract_ctx and extract_ctx.limits else ExtractLimits(self._config)
        with open(path, "rb") as handle:
            data = handle.read()
        limits.check_file_size(data)
        return self.extract_from_bytes(data, mime_type=mime_type, extract_ctx=extract_ctx)

    def extract_from_bytes(
        self,
        data: bytes,
        *,
        mime_type: str | None = None,
        extract_ctx: ExtractContext | None = None,
    ) -> ExtractResult:
        limits = extract_ctx.limits if extract_ctx and extract_ctx.limits else ExtractLimits(self._config)
        limits.check_file_size(data)
        text = data.decode("utf-8", errors="replace")
        limits.check_part_size(text)
        part = build_text_part(page_number=1, part_index=0, text=text, metadata={"source": "plain_text"})
        parts = [part] if text.strip() else []
        if extract_ctx is not None:
            extract_ctx.emit_parts(parts, batch_size=self._config.extract_batch_size)
            extract_ctx.flush()
        status = finalize_extract_status(
            parts=parts,
            failed_pages=0,
            warnings=[],
            counters=extract_ctx.counters if extract_ctx is not None else None,
        )
        if extract_ctx is not None and extract_ctx.streaming:
            return ExtractResult.from_counters(
                counters=extract_ctx.counters,
                total_pages=1,
                processed_pages=1,
                failed_pages=0,
                warnings=[],
                status=status,
                extractor_name=self.name,
                extractor_version=self.version,
                source_mime=mime_type or "text/plain",
            )
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
            text_parts_count=1 if text.strip() else 0,
        )


__all__ = ["ManualTextExtractorAdapter"]
