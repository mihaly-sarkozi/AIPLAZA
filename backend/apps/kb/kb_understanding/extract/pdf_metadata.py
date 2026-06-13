from __future__ import annotations

from typing import Any

from apps.kb.kb_understanding.extract.extract_metadata import build_base_metadata


def group_words_into_blocks(words: list[dict[str, Any]], *, page_height: float) -> list[dict[str, Any]]:
    if not words:
        return []

    sorted_words = sorted(words, key=lambda word: (round(word.get("top", 0), 1), word.get("x0", 0)))
    lines: list[list[dict[str, Any]]] = []
    current_line: list[dict[str, Any]] = []
    current_top: float | None = None

    for word in sorted_words:
        top = float(word.get("top", 0))
        if current_line and current_top is not None and abs(top - current_top) > 3:
            lines.append(current_line)
            current_line = [word]
            current_top = top
        else:
            current_line.append(word)
            current_top = top if current_top is None else current_top
    if current_line:
        lines.append(current_line)

    blocks: list[dict[str, Any]] = []
    current_block_lines: list[list[dict[str, Any]]] = []
    previous_bottom: float | None = None

    for line in lines:
        line_top = min(float(word.get("top", 0)) for word in line)
        if current_block_lines and previous_bottom is not None and (line_top - previous_bottom) > 14:
            blocks.append(_block_from_lines(current_block_lines, page_height=page_height, layout_order=len(blocks)))
            current_block_lines = []
        current_block_lines.append(line)
        previous_bottom = max(float(word.get("bottom", 0)) for word in line)

    if current_block_lines:
        blocks.append(_block_from_lines(current_block_lines, page_height=page_height, layout_order=len(blocks)))
    return blocks


def build_text_block_metadata(
    block: dict[str, Any],
    *,
    page_number: int,
    part_index: int,
    document_order: int,
) -> dict[str, Any]:
    font_names = list(block.get("font_names") or [])
    font_sizes = list(block.get("font_sizes") or [])
    is_bold = any("bold" in name.lower() for name in font_names)
    dominant_font_size = max(font_sizes) if font_sizes else None
    is_heading, heading_confidence = _heading_guess_with_confidence(
        block.get("text") or "",
        font_names=font_names,
        dominant_font_size=dominant_font_size,
        is_bold=is_bold,
    )
    header_footer = block.get("header_footer") or {}
    role = header_footer.get("role")
    header_footer_confidence = float(header_footer.get("confidence", 0.0) or 0.0)
    is_header_candidate = role == "header"
    is_footer_candidate = role == "footer"
    block_kind = _text_block_kind(
        is_heading=is_heading,
        is_header_candidate=is_header_candidate,
        is_footer_candidate=is_footer_candidate,
    )
    bbox = block.get("bbox")
    return build_base_metadata(
        source="pdf_text_layer",
        document_order=document_order,
        page_number=page_number,
        part_index=part_index,
        block_kind=block_kind,
        style={
            "font_names": font_names,
            "font_sizes": font_sizes,
            "dominant_font_size": dominant_font_size,
            "is_bold_guess": is_bold,
            "is_heading_guess": is_heading,
            "heading_confidence": heading_confidence,
        },
        layout={
            "bbox": bbox,
            "layout_order": block.get("layout_order"),
            "header_footer_confidence": header_footer_confidence,
            "is_header_candidate": is_header_candidate,
            "is_footer_candidate": is_footer_candidate,
            "heading_confidence": heading_confidence,
        },
        confidence=header_footer_confidence,
        extra={
            "font_names": font_names,
            "font_sizes": font_sizes,
            "dominant_font_size": dominant_font_size,
            "is_bold_guess": is_bold,
            "is_heading_guess": is_heading,
            "heading_confidence": heading_confidence,
            "is_header_candidate": is_header_candidate,
            "is_footer_candidate": is_footer_candidate,
            "header_footer_confidence": header_footer_confidence,
            "bbox": bbox,
            "layout_order": block.get("layout_order"),
        },
    )


def build_table_metadata(
    *,
    page_number: int,
    part_index: int,
    document_order: int,
    table_index: int,
    bbox: dict[str, float] | None,
    headers: list[str],
    rows: list[list[str]],
) -> dict[str, Any]:
    row_count = len(rows)
    column_count = len(headers) if headers else (len(rows[0]) if rows else 0)
    return build_base_metadata(
        source="pdf_table",
        document_order=document_order,
        page_number=page_number,
        part_index=part_index,
        block_kind="table",
        layout={"bbox": bbox, "table_index": table_index, "layout_order": table_index},
        extra={
            "row_count": row_count,
            "column_count": column_count,
            "headers": headers,
            "rows": rows,
            "table_index": table_index,
            "bbox": bbox,
        },
    )


def build_ocr_metadata(
    *,
    page_number: int,
    part_index: int,
    document_order: int,
    ocr_engine: str,
    ocr_language: str,
    ocr_confidence: float,
) -> dict[str, Any]:
    return build_base_metadata(
        source="ocr",
        document_order=document_order,
        page_number=page_number,
        part_index=part_index,
        block_kind="ocr_text",
        confidence=ocr_confidence,
        extra={
            "ocr_engine": ocr_engine,
            "ocr_language": ocr_language,
            "ocr_confidence": ocr_confidence,
        },
    )


def _block_from_lines(lines: list[list[dict[str, Any]]], *, page_height: float, layout_order: int) -> dict[str, Any]:
    words = [word for line in lines for word in line]
    text = " ".join(word.get("text", "") for word in words).strip()
    if words:
        x0 = min(float(word.get("x0", 0)) for word in words)
        x1 = max(float(word.get("x1", 0)) for word in words)
        top = min(float(word.get("top", 0)) for word in words)
        bottom = max(float(word.get("bottom", 0)) for word in words)
        bbox = {"x0": x0, "y0": top, "x1": x1, "y1": bottom}
    else:
        bbox = None
    font_names = sorted({str(word.get("fontname") or "") for word in words if word.get("fontname")})
    font_sizes = sorted({round(float(word.get("size") or 0), 2) for word in words if word.get("size")})
    return {
        "text": text,
        "bbox": bbox,
        "font_names": font_names,
        "font_sizes": font_sizes,
        "layout_order": layout_order,
        "header_footer": _header_footer_guess(top=bbox["y0"], bottom=bbox["y1"], page_height=page_height) if bbox else {"role": None, "confidence": 0.0},
    }


def _header_footer_guess(*, top: float, bottom: float, page_height: float) -> dict[str, Any]:
    if page_height <= 0:
        return {"role": None, "confidence": 0.0}
    top_ratio = top / page_height
    bottom_ratio = bottom / page_height
    if top_ratio <= 0.1:
        confidence = min(1.0, 0.5 + (0.1 - top_ratio) * 5)
        return {"role": "header", "confidence": round(confidence, 2)}
    if bottom_ratio >= 0.9:
        confidence = min(1.0, 0.5 + (bottom_ratio - 0.9) * 5)
        return {"role": "footer", "confidence": round(confidence, 2)}
    return {"role": None, "confidence": 0.0}


def _heading_guess_with_confidence(
    text: str,
    *,
    font_names: list[str],
    dominant_font_size: float | None,
    is_bold: bool,
) -> tuple[bool, float]:
    line = text.strip()
    if not line or len(line) > 120:
        return False, 0.0
    confidence = 0.0
    if is_bold and len(line.split()) <= 12:
        confidence = max(confidence, 0.72)
    if dominant_font_size is not None and dominant_font_size >= 14 and len(line.split()) <= 10:
        confidence = max(confidence, 0.74)
    if len(line.split()) <= 6 and not any(char in line for char in ".!?"):
        confidence = max(confidence, 0.55)
    return confidence >= 0.55, round(confidence, 2)


def _text_block_kind(*, is_heading: bool, is_header_candidate: bool, is_footer_candidate: bool) -> str:
    if is_header_candidate:
        return "header"
    if is_footer_candidate:
        return "footer"
    if is_heading:
        return "heading"
    return "paragraph"


__all__ = [
    "build_ocr_metadata",
    "build_table_metadata",
    "build_text_block_metadata",
    "group_words_into_blocks",
]
