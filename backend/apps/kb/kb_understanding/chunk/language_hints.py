from __future__ import annotations

_OCR_LANG_MAP = {
    "hun": "hu",
    "hu": "hu",
    "eng": "en",
    "en": "en",
    "spa": "es",
    "es": "es",
}


def parse_ocr_language_hints(raw: str | None) -> list[str]:
    if not raw:
        return []
    hints: list[str] = []
    for part in raw.split("+"):
        mapped = _OCR_LANG_MAP.get(part.strip().lower())
        if mapped and mapped not in hints:
            hints.append(mapped)
    return hints


def collect_language_hint_fields(
    *,
    is_from_ocr: bool,
    ocr_language_values: list[str | None],
    has_extractor_parts: bool,
) -> tuple[list[str], list[str], list[str]]:
    hints: list[str] = []
    sources: list[str] = []
    ocr_languages: list[str] = []

    if is_from_ocr:
        sources.append("ocr")
    if has_extractor_parts and not is_from_ocr:
        sources.append("extractor")
    elif has_extractor_parts and is_from_ocr:
        if "extractor" not in sources:
            sources.append("extractor")

    for raw in ocr_language_values:
        if not raw:
            continue
        if raw not in ocr_languages:
            ocr_languages.append(raw)
        for hint in parse_ocr_language_hints(raw):
            if hint not in hints:
                hints.append(hint)

    return hints, sources, ocr_languages


__all__ = ["collect_language_hint_fields", "parse_ocr_language_hints"]
