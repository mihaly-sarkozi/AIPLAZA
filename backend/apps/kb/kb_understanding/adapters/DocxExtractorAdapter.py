from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.extract.extract_limits import ExtractLimits, finalize_extract_status
from apps.kb.kb_understanding.extract.part_builder import build_table_part, build_text_part, summarize_parts


class DocxExtractorAdapter:
    name = "python_docx"
    version = "2.0"

    def __init__(self, *, config: ExtractConfig | None = None) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        from shared.documents.text_extraction import extract_document_from_upload

        limits = ExtractLimits(self._config)
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
        table_page = None

        def flush_table() -> None:
            nonlocal part_index, table_buffer, table_headers, table_page
            if not table_buffer and not table_headers:
                return
            rows = table_buffer
            headers = table_headers
            if headers and rows and rows[0] == headers:
                rows = rows[1:]
            parts.append(
                build_table_part(
                    page_number=table_page,
                    part_index=part_index,
                    headers=headers,
                    rows=rows,
                    source="docx_table",
                    metadata={"section_index": section_index},
                )
            )
            part_index += 1
            table_buffer = []
            table_headers = []

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
            page_number = paragraph.page_number or section_index
            limits.check_part_size(text)
            parts.append(
                build_text_part(
                    page_number=page_number,
                    part_index=part_index,
                    text=text,
                    metadata={
                        "block_type": paragraph.block_type,
                        "source": "docx_paragraph",
                    },
                )
            )
            part_index += 1

        flush_table()

        status = finalize_extract_status(parts=parts, failed_pages=0, warnings=warnings)
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
        )


__all__ = ["DocxExtractorAdapter"]
