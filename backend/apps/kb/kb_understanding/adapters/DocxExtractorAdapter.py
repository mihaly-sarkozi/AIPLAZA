from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_context import ExtractContext
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.part_builder import build_table_part, build_text_part, summarize_parts


class DocxExtractorAdapter:
    name = "python_docx"
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
        with open(path, "rb") as handle:
            return self.extract_from_bytes(handle.read(), mime_type=mime_type, extract_ctx=extract_ctx)

    def extract_from_bytes(
        self,
        data: bytes,
        *,
        mime_type: str | None = None,
        extract_ctx: ExtractContext | None = None,
    ) -> ExtractResult:
        from shared.documents.text_extraction import extract_document_from_upload

        limits = extract_ctx.limits if extract_ctx and extract_ctx.limits else ExtractLimits(self._config)
        limits.check_file_size(data)

        try:
            document = extract_document_from_upload("input.docx", data)
        except Exception as exc:
            raise UnderstandingProcessingError(UnderstandingErrorCode.EXTRACTION_FAILED) from exc

        parts: list[ExtractPart] = []
        warnings: list[str] = []
        part_index = 0
        section_index = 0
        table_buffer: list[list[str]] = []
        table_headers: list[str] = []

        def flush_table() -> None:
            nonlocal part_index, table_buffer, table_headers
            if not table_buffer and not table_headers:
                return
            rows = table_buffer
            headers = table_headers
            if headers and rows and rows[0] == headers:
                rows = rows[1:]
            part = build_table_part(
                page_number=section_index,
                part_index=part_index,
                headers=headers,
                rows=rows,
                source="docx_table",
                metadata={"section_index": section_index},
            )
            _emit([part])
            part_index += 1
            table_buffer = []
            table_headers = []

        def _emit(batch: list[ExtractPart]) -> None:
            if extract_ctx is not None:
                extract_ctx.emit_parts(batch, batch_size=self._config.extract_batch_size)
            else:
                parts.extend(batch)

        for paragraph in document.paragraphs:
            limits.check_duration()
            text = (paragraph.text or "").strip()
            if not text:
                continue

            if paragraph.block_type == "table_row":
                cells = [str(cell).strip() for cell in (paragraph.metadata or {}).get("table_cells") or []]
                cells = [cell for cell in cells if cell]
                if not cells:
                    continue
                role = (paragraph.metadata or {}).get("table_role")
                if role == "header" and not table_headers:
                    table_headers = cells
                    table_buffer = [cells]
                else:
                    table_buffer.append(cells)
                continue

            flush_table()
            section_index += 1
            limits.check_part_size(text)
            _emit(
                [
                    build_text_part(
                        page_number=paragraph.page_number or section_index,
                        part_index=part_index,
                        text=text,
                        metadata={
                            "block_type": paragraph.block_type,
                            "source": "docx_paragraph",
                        },
                    )
                ]
            )
            part_index += 1

        flush_table()
        if extract_ctx is not None:
            extract_ctx.flush()

        status = finalize_extract_status(
            parts=parts,
            failed_pages=0,
            warnings=warnings,
            counters=extract_ctx.counters if extract_ctx is not None else None,
        )
        if extract_ctx is not None and extract_ctx.streaming:
            return ExtractResult.from_counters(
                counters=extract_ctx.counters,
                total_pages=max(section_index, 1),
                processed_pages=max(section_index, 1),
                failed_pages=0,
                warnings=warnings,
                status=status,
                extractor_name=self.name,
                extractor_version=self.version,
                source_mime=mime_type
                or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        return ExtractResult(
            total_pages=max(section_index, 1),
            parts=parts,
            total_chars=summarize_parts(parts),
            warnings=warnings,
            status=status,
            extractor_name=self.name,
            extractor_version=self.version,
            processed_pages=max(section_index, 1),
            failed_pages=0,
            source_mime=mime_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            text_parts_count=sum(1 for part in parts if part.part_type == "TEXT"),
            table_parts_count=sum(1 for part in parts if part.part_type == "TABLE"),
        )


__all__ = ["DocxExtractorAdapter"]
