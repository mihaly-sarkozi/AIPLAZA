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
    font_names = block.get("font_names") or []
    font_sizes = block.get("font_sizes") or []
    is_bold = any("bold" in name.lower() for name in font_names)
    avg_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0.0
    is_heading = _heading_guess(block.get("text") or "", font_names=font_names, avg_size=avg_size)
    header_footer = block.get("header_footer") or {}
    block_kind = _text_block_kind(
        is_heading=is_heading,
        header_footer=header_footer,
    )
    return build_base_metadata(
        source="pdf_text_layer",
        document_order=document_order,
        page_number=page_number,
        part_index=part_index,
        block_kind=block_kind,
        style={
            "font_names": font_names,
            "font_sizes": font_sizes,
            "is_bold_guess": is_bold,
            "is_heading_guess": is_heading,
        },
        layout={
            "bbox": block.get("bbox"),
            "layout_order": block.get("layout_order"),
            "header_footer_confidence": header_footer.get("confidence", 0.0),
            "header_footer_role": header_footer.get("role"),
        },
        confidence=float(header_footer.get("confidence", 0.0) or 0.0),
        extra={
            "font_names": font_names,
            "font_sizes": font_sizes,
            "is_bold_guess": is_bold,
            "is_heading_guess": is_heading,
            "bbox": block.get("bbox"),
            "layout_order": block.get("layout_order"),
            "header_footer_confidence": header_footer.get("confidence", 0.0),
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
    return build_base_metadata(
        source="pdf_table",
        document_order=document_order,
        page_number=page_number,
        part_index=part_index,
        block_kind="table",
        layout={"bbox": bbox, "table_index": table_index, "layout_order": table_index},
        extra={
            "row_count": len(rows),
            "column_count": len(headers) if headers else (len(rows[0]) if rows else 0),
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
    x0 = min(float(word.get("x0", 0)) for word in words)
    x1 = max(float(word.get("x1", 0)) for word in words)
    top = min(float(word.get("top", 0)) for word in words)
    bottom = max(float(word.get("bottom", 0)) for word in words)
    font_names = sorted({str(word.get("fontname") or "") for word in words if word.get("fontname")})
    font_sizes = sorted({round(float(word.get("size") or 0), 2) for word in words if word.get("size")})
    return {
        "text": text,
        "bbox": {"x0": x0, "y0": top, "x1": x1, "y1": bottom},
        "font_names": font_names,
        "font_sizes": font_sizes,
        "layout_order": layout_order,
        "header_footer": _header_footer_guess(top=top, bottom=bottom, page_height=page_height),
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


def _heading_guess(text: str, *, font_names: list[str], avg_size: float) -> bool:
    line = text.strip()
    if not line or len(line) > 120:
        return False
    if any("bold" in name.lower() for name in font_names) and len(line.split()) <= 12:
        return True
    return avg_size >= 14 and len(line.split()) <= 10


def _text_block_kind(*, is_heading: bool, header_footer: dict[str, Any]) -> str:
    role = header_footer.get("role")
    if role == "header":
        return "header"
    if role == "footer":
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
