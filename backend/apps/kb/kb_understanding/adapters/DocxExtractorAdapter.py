from __future__ import annotations

# backend/apps/kb/kb_understanding/adapters/DocxExtractorAdapter.py
# Feladat: DOCX szövegkinyerés (a shared python-docx extrakcióra építve).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError


class DocxExtractorAdapter:
    name = "python_docx_v1"

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractedContentDto:
        from shared.documents.text_extraction import extract_document_from_upload

        try:
            document = extract_document_from_upload("input.docx", data)
        except Exception as exc:
            raise UnderstandingProcessingError(UnderstandingErrorCode.EXTRACTION_FAILED) from exc

        text = document.text_content
        return ExtractedContentDto(
            text=text,
            page_map=[],
            char_count=len(text),
            source_mime=mime_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            extractor=self.name,
        )


__all__ = ["DocxExtractorAdapter"]
