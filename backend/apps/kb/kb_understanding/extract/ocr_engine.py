from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.config.ExtractConfig import ExtractConfig


@dataclass(frozen=True)
class OcrEngineStatus:
    available: bool
    engine_found: bool
    language_packs_ok: bool
    missing_language_packs: tuple[str, ...] = ()
    error_message: str | None = None


@dataclass
class OcrExtractStats:
    pdf_pages_ocr_scanned: int = 0
    docx_images_ocr_scanned: int = 0
    ocr_engine_available: bool = False
    ocr_language: str = ""

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "pdf_pages_ocr_scanned": self.pdf_pages_ocr_scanned,
            "docx_images_ocr_scanned": self.docx_images_ocr_scanned,
            "ocr_language": self.ocr_language,
            "ocr_engine_available": self.ocr_engine_available,
        }


def required_language_packs(config: ExtractConfig) -> tuple[str, ...]:
    packs = [part.strip() for part in config.ocr_languages.split("+") if part.strip()]
    return tuple(packs or ("hun", "eng", "spa"))


def check_ocr_engine(config: ExtractConfig) -> OcrEngineStatus:
    if not config.ocr_enabled:
        return OcrEngineStatus(
            available=False,
            engine_found=False,
            language_packs_ok=False,
            error_message="ocr_disabled",
        )

    if shutil.which("tesseract") is None:
        return OcrEngineStatus(
            available=False,
            engine_found=False,
            language_packs_ok=False,
            error_message="tesseract binary not found",
        )

    try:
        import pytesseract
    except ImportError:
        return OcrEngineStatus(
            available=False,
            engine_found=True,
            language_packs_ok=False,
            error_message="pytesseract not installed",
        )

    try:
        installed = {lang.strip() for lang in pytesseract.get_languages(config="") if lang.strip()}
    except Exception as exc:
        return OcrEngineStatus(
            available=False,
            engine_found=True,
            language_packs_ok=False,
            error_message=str(exc)[:500],
        )

    required = required_language_packs(config)
    missing = tuple(lang for lang in required if lang not in installed)
    if missing:
        return OcrEngineStatus(
            available=False,
            engine_found=True,
            language_packs_ok=False,
            missing_language_packs=missing,
            error_message=f"missing language packs: {', '.join(missing)}",
        )

    return OcrEngineStatus(
        available=True,
        engine_found=True,
        language_packs_ok=True,
    )


def normalize_ocr_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_duplicate_ocr_text(ocr_text: str, existing_text: str, *, deduplicate: bool = True) -> bool:
    if not deduplicate:
        return False
    ocr_norm = normalize_ocr_text(ocr_text)
    if not ocr_norm:
        return True
    existing_norm = normalize_ocr_text(existing_text)
    if not existing_norm:
        return False
    if ocr_norm in existing_norm or existing_norm in ocr_norm:
        return True
    ocr_words = set(ocr_norm.split())
    existing_words = set(existing_norm.split())
    if not ocr_words:
        return True
    overlap = len(ocr_words & existing_words) / len(ocr_words)
    return overlap >= 0.9


def resize_image_if_needed(image, *, max_pixels: int):
    width, height = image.size
    pixels = width * height
    if pixels <= max_pixels:
        return image
    scale = (max_pixels / pixels) ** 0.5
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return image.resize(new_size)


__all__ = [
    "OcrEngineStatus",
    "OcrExtractStats",
    "check_ocr_engine",
    "is_duplicate_ocr_text",
    "normalize_ocr_text",
    "required_language_packs",
    "resize_image_if_needed",
]
