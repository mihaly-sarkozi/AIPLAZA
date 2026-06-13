from __future__ import annotations

from apps.kb.kb_understanding.config.ExtractConfig import ExtractConfig, DEFAULT_EXTRACT_CONFIG
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.dto.ExtractResultDto import ExtractResult
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode


class OcrExtractorAdapter:
    name = "tesseract"
    version = "1.0"

    def __init__(self, config: ExtractConfig | None = None) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG

    def ocr_page_image(self, image, *, page_number: int, part_index: int) -> ExtractPart:
        metadata = {
            "ocr_engine": "tesseract",
            "ocr_language": self._config.ocr_language,
            "source": "pdf_page_image",
        }
        try:
            import pytesseract
        except ImportError:
            return ExtractPart(
                part_type=ExtractPartType.OCR_FAILED.value,
                page_number=page_number,
                part_index=part_index,
                text=None,
                char_count=0,
                status="failed",
                error_code=UnderstandingErrorCode.OCR_UNAVAILABLE.value,
                error_message="pytesseract not installed",
                metadata=metadata,
            )

        try:
            raw = pytesseract.image_to_data(
                image,
                lang=self._config.ocr_language,
                output_type=pytesseract.Output.DICT,
            )
            text = pytesseract.image_to_string(image, lang=self._config.ocr_language).strip()
            confidences = [
                float(value)
                for value in raw.get("conf", [])
                if str(value).strip() not in {"", "-1"}
            ]
            confidence = round(sum(confidences) / len(confidences) / 100.0, 4) if confidences else 0.0
            metadata["ocr_confidence"] = confidence
            if not text:
                return ExtractPart(
                    part_type=ExtractPartType.OCR_EMPTY.value,
                    page_number=page_number,
                    part_index=part_index,
                    text="",
                    char_count=0,
                    metadata=metadata,
                )
            return ExtractPart(
                part_type=ExtractPartType.OCR_TEXT.value,
                page_number=page_number,
                part_index=part_index,
                text=text,
                char_count=len(text),
                metadata=metadata,
            )
        except Exception as exc:
            return ExtractPart(
                part_type=ExtractPartType.OCR_FAILED.value,
                page_number=page_number,
                part_index=part_index,
                text=None,
                char_count=0,
                status="failed",
                error_code=UnderstandingErrorCode.OCR_FAILED.value,
                error_message=str(exc)[:1000],
                metadata=metadata,
            )


__all__ = ["OcrExtractorAdapter"]
