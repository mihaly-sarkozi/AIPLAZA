from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.kb.kb_understanding.adapters.OcrExtractorAdapter import OcrExtractorAdapter
from apps.kb.kb_understanding.adapters.PdfExtractorAdapter import PdfExtractorAdapter
from apps.kb.kb_understanding.config.ExtractConfig import ExtractConfig
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.extract.ocr_engine import (
    OcrEngineStatus,
    check_ocr_engine,
    is_duplicate_ocr_text,
)


def test_extract_config_ocr_languages_default_hun_eng_spa() -> None:
    config = ExtractConfig()
    assert config.ocr_languages == "hun+eng+spa"
    assert config.ocr_language == "hun+eng+spa"


def test_is_duplicate_ocr_text_detects_overlap() -> None:
    existing = "Ez egy hosszabb szöveg a PDF text layerben található tartalommal."
    ocr = "Ez egy hosszabb szöveg a PDF text layerben"
    assert is_duplicate_ocr_text(ocr, existing, deduplicate=True) is True


def test_is_duplicate_ocr_text_keeps_new_information() -> None:
    existing = "Text layer content only."
    ocr = "Image caption with completely different words and numbers 12345."
    assert is_duplicate_ocr_text(ocr, existing, deduplicate=True) is False


def test_is_duplicate_respects_disabled_deduplicate() -> None:
    assert is_duplicate_ocr_text("same text", "same text", deduplicate=False) is False


@patch("apps.kb.kb_understanding.extract.ocr_engine.shutil.which", return_value=None)
def test_check_ocr_engine_reports_missing_tesseract(_which: MagicMock) -> None:
    status = check_ocr_engine(ExtractConfig())
    assert status.available is False
    assert status.engine_found is False


def test_ocr_adapter_engine_unavailable_emits_single_failed_part() -> None:
    config = ExtractConfig(ocr_enabled=True)
    adapter = OcrExtractorAdapter(config)
    adapter._status = OcrEngineStatus(
        available=False,
        engine_found=False,
        language_packs_ok=False,
        error_message="tesseract binary not found",
    )
    adapter._engine_failure_emitted = False

    image = MagicMock()
    first = adapter.ocr_page_image(image, page_number=1, part_index=0, document_order=0)
    second = adapter.ocr_page_image(image, page_number=2, part_index=1, document_order=1)

    assert first is not None
    assert first.part_type == ExtractPartType.OCR_FAILED.value
    assert first.error_code == UnderstandingErrorCode.OCR_ENGINE_UNAVAILABLE.value
    assert second is None


def test_pdf_should_run_page_ocr_for_pages_with_images() -> None:
    adapter = PdfExtractorAdapter(
        config=ExtractConfig(ocr_run_on_pdf_images=True, ocr_run_on_low_text_pdf_pages=False),
    )
    page = MagicMock()
    page.images = [{"x0": 0, "top": 0, "x1": 10, "bottom": 10}]
    should_run, reason = adapter._should_run_page_ocr(page, text_chars=500)
    assert should_run is True
    assert reason == "page_contains_images"


def test_pdf_should_run_page_ocr_for_low_text_without_images() -> None:
    adapter = PdfExtractorAdapter(
        config=ExtractConfig(
            ocr_min_text_chars=50,
            ocr_run_on_pdf_images=False,
            ocr_run_on_low_text_pdf_pages=True,
        ),
    )
    page = MagicMock()
    page.images = []
    should_run, reason = adapter._should_run_page_ocr(page, text_chars=10)
    assert should_run is True
    assert reason == "low_text_layer"


@patch("pdfplumber.open")
@patch.object(PdfExtractorAdapter, "_extract_page")
def test_pdf_passes_ocr_stats_to_extract_page(
    extract_page_mock: MagicMock,
    pdfplumber_open_mock: MagicMock,
) -> None:
    page = MagicMock()
    page.images = []
    pdf = MagicMock()
    pdf.pages = [page]
    pdfplumber_open_mock.return_value.__enter__.return_value = pdf

    extract_page_mock.return_value = ([], False, 0, 0)
    adapter = PdfExtractorAdapter(config=ExtractConfig(), ocr_extractor=MagicMock())
    adapter.extract(b"%PDF-1.4")

    extract_page_mock.assert_called_once()
    assert extract_page_mock.call_args.kwargs["ocr_stats"] is not None
