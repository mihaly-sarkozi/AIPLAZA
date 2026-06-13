"""Extract lépés: adapter-választás, storage hiba, üres tartalom, perzisztálás."""
from __future__ import annotations

import pytest

from apps.kb.kb_understanding.adapters.ManualTextExtractorAdapter import ManualTextExtractorAdapter
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.dto.ExtractedContentDto import ExtractedContentDto
from apps.kb.kb_understanding.enums.ExtractStatus import ExtractStatus
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.errors.UnderstandingValidationError import UnderstandingValidationError
from apps.kb.kb_understanding.extract.part_builder import build_text_part
from apps.kb.kb_understanding.service.ExtractContentService import ExtractContentService

from tests.unit.kb.understanding.conftest import FakeContentRepository

pytestmark = pytest.mark.unit


class _FakeStorage:
    def __init__(self, data: bytes = b"hello", error: Exception | None = None) -> None:
        self._data = data
        self._error = error

    def read_bytes(self, *, raw_ref: str) -> bytes:
        if self._error is not None:
            raise self._error
        return self._data

    def stat_bytes(self, *, raw_ref: str) -> int:
        if self._error is not None:
            raise self._error
        return len(self._data)


class _MarkerExtractor:
    def __init__(self, name: str) -> None:
        self.name = name
        self.version = "1.0"
        self.called = False

    def extract(self, data: bytes, *, mime_type: str | None = None) -> ExtractResult:
        return self.extract_from_bytes(data, mime_type=mime_type)

    def extract_from_bytes(self, data: bytes, *, mime_type: str | None = None, extract_ctx=None) -> ExtractResult:
        self.called = True
        part = build_text_part(page_number=1, part_index=0, text=f"{self.name}-text")
        return ExtractResult(
            total_pages=1,
            parts=[part],
            total_chars=len(part.text or ""),
            warnings=[],
            status=ExtractStatus.COMPLETED.value,
            extractor_name=self.name,
            extractor_version=self.version,
            processed_pages=1,
            failed_pages=0,
            text_parts_count=1,
        )


def _service(storage=None):
    repo = FakeContentRepository()
    pdf = _MarkerExtractor("pdf")
    docx = _MarkerExtractor("docx")
    text = _MarkerExtractor("text")
    service = ExtractContentService(
        repo,
        storage or _FakeStorage(),
        pdf_extractor=pdf,
        docx_extractor=docx,
        text_extractor=text,
    )
    return service, repo, pdf, docx, text


def _ctx_with(ctx, **overrides):
    from dataclasses import replace

    return replace(ctx, **overrides)


def test_manual_text_extractor_decodes_utf8():
    result = ManualTextExtractorAdapter().extract("árvíztűrő".encode("utf-8"))
    assert result.parts[0].text == "árvíztűrő"
    assert result.total_chars == len("árvíztűrő")
    assert result.extractor_name == "plain_text"


def test_extract_selects_text_adapter_for_text_mime(ctx):
    service, repo, pdf, docx, text = _service()
    result = service.run(ctx)
    assert text.called and not pdf.called and not docx.called
    assert result.extractor == "text"
    assert repo.extracted[ctx.training_item_id] is not None
    assert repo.parts[ctx.training_item_id]


def test_extract_selects_pdf_adapter_by_mime(ctx):
    service, _, pdf, _, _ = _service()
    service.run(_ctx_with(ctx, mime_type="application/pdf", file_name="a.pdf"))
    assert pdf.called


def test_extract_selects_docx_adapter_by_filename(ctx):
    service, _, _, docx, _ = _service()
    service.run(_ctx_with(ctx, mime_type=None, file_name="doc.docx"))
    assert docx.called


def test_extract_unsupported_mime_raises(ctx):
    service, _, _, _, _ = _service()
    with pytest.raises(UnderstandingProcessingError) as excinfo:
        service.run(_ctx_with(ctx, mime_type="image/png", file_name="kep.png"))
    assert excinfo.value.code == UnderstandingErrorCode.UNSUPPORTED_CONTENT_TYPE.value


def test_extract_storage_error_is_retryable(ctx):
    service, _, _, _, _ = _service(storage=_FakeStorage(error=RuntimeError("io")))
    with pytest.raises(UnderstandingProcessingError) as excinfo:
        service.run(ctx)
    assert excinfo.value.code == UnderstandingErrorCode.STORAGE_ERROR.value
    assert excinfo.value.retryable is True


def test_extract_empty_content_fails_validation(ctx):
    class _EmptyExtractor:
        name = "empty"
        version = "1.0"

        def extract(self, data, *, mime_type=None):
            return ExtractResult(
                total_pages=0,
                parts=[],
                total_chars=0,
                warnings=[],
                status=ExtractStatus.FAILED.value,
                extractor_name=self.name,
            )

    repo = FakeContentRepository()
    service = ExtractContentService(
        repo,
        _FakeStorage(),
        pdf_extractor=_EmptyExtractor(),
        docx_extractor=_EmptyExtractor(),
        text_extractor=_EmptyExtractor(),
    )
    with pytest.raises(UnderstandingValidationError) as excinfo:
        service.run(ctx)
    assert excinfo.value.code == UnderstandingErrorCode.EMPTY_CONTENT.value
    assert repo.extracted == {}
