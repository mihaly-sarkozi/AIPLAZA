from __future__ import annotations

from typing import Any

from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG, ExtractConfig
from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.extract.ocr_engine import (
    OcrEngineStatus,
    check_ocr_engine,
    is_duplicate_ocr_text,
    resize_image_if_needed,
)


class OcrExtractorAdapter:
    name = "tesseract"
    version = "2.0"

    def __init__(self, config: ExtractConfig | None = None) -> None:
        self._config = config or DEFAULT_EXTRACT_CONFIG
        self._status = check_ocr_engine(self._config)
        self._engine_failure_emitted = False

    @property
    def engine_status(self) -> OcrEngineStatus:
        return self._status

    @property
    def is_available(self) -> bool:
        return self._status.available

    def ocr_page_image(
        self,
        image,
        *,
        page_number: int,
        part_index: int,
        document_order: int = 0,
        reason: str = "page_contains_images",
        existing_text: str = "",
    ) -> ExtractPart | None:
        return self._ocr_image(
            image,
            page_number=page_number,
            part_index=part_index,
            document_order=document_order,
            source="pdf_page_ocr",
            reason=reason,
            existing_text=existing_text,
        )

    def ocr_pdf_embedded_image(
        self,
        image,
        *,
        page_number: int,
        part_index: int,
        document_order: int,
        existing_text: str = "",
    ) -> ExtractPart | None:
        return self._ocr_image(
            image,
            page_number=page_number,
            part_index=part_index,
            document_order=document_order,
            source="pdf_embedded_image_ocr",
            reason="embedded_image",
            existing_text=existing_text,
        )

    def ocr_embedded_image(
        self,
        image,
        *,
        part_index: int,
        document_order: int,
        image_name: str,
        page_number: int | None = None,
    ) -> ExtractPart | None:
        return self._ocr_image(
            image,
            page_number=page_number,
            part_index=part_index,
            document_order=document_order,
            source="docx_embedded_image_ocr",
            reason="docx_embedded_image",
            image_name=image_name,
        )

    def _ocr_image(
        self,
        image,
        *,
        page_number: int | None,
        part_index: int,
        document_order: int,
        source: str,
        reason: str,
        existing_text: str = "",
        image_name: str | None = None,
    ) -> ExtractPart | None:
        if not self._config.ocr_enabled:
            return None

        metadata = self._base_metadata(
            page_number=page_number,
            part_index=part_index,
            document_order=document_order,
            source=source,
            reason=reason,
            image_name=image_name,
        )

        if not self._status.engine_found:
            if self._engine_failure_emitted:
                return None
            self._engine_failure_emitted = True
            return ExtractPart(
                part_type=ExtractPartType.OCR_FAILED.value,
                page_number=page_number,
                part_index=part_index,
                text=None,
                char_count=0,
                status="failed",
                error_code=UnderstandingErrorCode.OCR_ENGINE_UNAVAILABLE.value,
                error_message=self._status.error_message or "tesseract not available",
                metadata=metadata,
            )

        if not self._status.language_packs_ok:
            if self._engine_failure_emitted:
                return None
            self._engine_failure_emitted = True
            return ExtractPart(
                part_type=ExtractPartType.OCR_FAILED.value,
                page_number=page_number,
                part_index=part_index,
                text=None,
                char_count=0,
                status="failed",
                error_code=UnderstandingErrorCode.OCR_LANGUAGE_PACK_MISSING.value,
                error_message=self._status.error_message or "missing OCR language packs",
                metadata=metadata,
            )

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
                error_code=UnderstandingErrorCode.OCR_ENGINE_UNAVAILABLE.value,
                error_message="pytesseract not installed",
                metadata=metadata,
            )

        try:
            prepared = resize_image_if_needed(image, max_pixels=self._config.ocr_max_image_pixels)
            raw = pytesseract.image_to_data(
                prepared,
                lang=self._config.ocr_languages,
                output_type=pytesseract.Output.DICT,
                timeout=self._config.ocr_timeout_seconds,
            )
            text = pytesseract.image_to_string(
                prepared,
                lang=self._config.ocr_languages,
                timeout=self._config.ocr_timeout_seconds,
            ).strip()
            confidences = [
                float(value)
                for value in raw.get("conf", [])
                if str(value).strip() not in {"", "-1"}
            ]
            confidence = round(sum(confidences) / len(confidences) / 100.0, 4) if confidences else 0.0
            metadata["ocr_confidence"] = confidence

            if confidence < self._config.ocr_min_confidence and text:
                return None

            if not text:
                return ExtractPart(
                    part_type=ExtractPartType.OCR_EMPTY.value,
                    page_number=page_number,
                    part_index=part_index,
                    text="",
                    char_count=0,
                    metadata=metadata,
                )

            if self._config.ocr_deduplicate and is_duplicate_ocr_text(
                text, existing_text, deduplicate=self._config.ocr_deduplicate
            ):
                return None

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

    def _base_metadata(
        self,
        *,
        page_number: int | None,
        part_index: int,
        document_order: int,
        source: str,
        reason: str,
        image_name: str | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "source": source,
            "ocr_engine": self.name,
            "ocr_language": self._config.ocr_languages,
            "page_number": page_number,
            "part_index": part_index,
            "document_order": document_order,
            "block_kind": "ocr_text",
            "reason": reason,
        }
        if image_name:
            metadata["image_name"] = image_name
        return metadata


__all__ = ["OcrExtractorAdapter"]
