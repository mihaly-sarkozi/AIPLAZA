from __future__ import annotations

from typing import Any


def build_base_metadata(
    *,
    source: str,
    document_order: int,
    page_number: int | None,
    part_index: int,
    block_kind: str,
    style: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
    confidence: float = 0.0,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": source,
        "document_order": document_order,
        "page_number": page_number,
        "part_index": part_index,
        "block_kind": block_kind,
        "style": dict(style or {}),
        "layout": dict(layout or {}),
        "confidence": confidence,
    }
    if extra:
        metadata.update(extra)
    return metadata


def merge_metadata(base: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = dict(base)
    if not extra:
        return merged
    for key, value in extra.items():
        if key in {"style", "layout"} and isinstance(value, dict):
            nested = dict(merged.get(key) or {})
            nested.update(value)
            merged[key] = nested
        else:
            merged[key] = value
    return merged


_DOWNSTREAM_KEYS = (
    "source",
    "document_order",
    "page_number",
    "part_index",
    "part_type",
    "block_kind",
    "style_name",
    "style_id",
    "heading_level",
    "heading_path",
    "heading_levels",
    "current_section_title",
    "is_heading",
    "is_list",
    "list_level",
    "numbering_id",
    "numbering_level",
    "list_marker",
    "runs",
    "bbox",
    "font_names",
    "font_sizes",
    "dominant_font_size",
    "is_bold_guess",
    "is_heading_guess",
    "heading_confidence",
    "is_header_candidate",
    "is_footer_candidate",
    "header_footer_confidence",
    "table_index",
    "row_count",
    "column_count",
    "headers",
    "rows",
    "ocr_engine",
    "ocr_language",
    "ocr_confidence",
    "is_from_ocr",
    "layout_order",
    "section_index",
)


def slim_metadata_for_downstream(metadata: dict[str, Any]) -> dict[str, Any]:
    slim: dict[str, Any] = {}
    for key in _DOWNSTREAM_KEYS:
        if key in metadata:
            slim[key] = metadata[key]

    style = metadata.get("style")
    if isinstance(style, dict):
        for nested_key in ("style_name", "style_id", "heading_level", "font_names", "font_sizes", "is_bold_guess", "is_heading_guess"):
            if nested_key in style and nested_key not in slim:
                slim[nested_key] = style[nested_key]

    layout = metadata.get("layout")
    if isinstance(layout, dict):
        for nested_key in (
            "bbox",
            "layout_order",
            "header_footer_confidence",
            "is_header_candidate",
            "is_footer_candidate",
            "heading_confidence",
        ):
            if nested_key in layout and nested_key not in slim:
                slim[nested_key] = layout[nested_key]

    if "bbox" not in slim:
        slim["bbox"] = metadata.get("bbox")
    if "font_names" not in slim:
        slim["font_names"] = metadata.get("font_names") or []
    if "font_sizes" not in slim:
        slim["font_sizes"] = metadata.get("font_sizes") or []
    if "dominant_font_size" not in slim and metadata.get("font_sizes"):
        sizes = metadata.get("font_sizes") or []
        slim["dominant_font_size"] = max(sizes) if sizes else None
    elif "dominant_font_size" not in slim:
        slim["dominant_font_size"] = metadata.get("dominant_font_size")

    if "is_from_ocr" not in slim and is_ocr_source(metadata):
        slim["is_from_ocr"] = True

    return slim


def is_ocr_source(metadata: dict[str, Any]) -> bool:
    if metadata.get("is_from_ocr"):
        return True
    part_type = str(metadata.get("part_type") or "").upper()
    block_kind = str(metadata.get("block_kind") or "").lower()
    source = str(metadata.get("source") or "").lower()
    return part_type == "OCR_TEXT" or block_kind == "ocr_text" or source.startswith("ocr")


__all__ = ["build_base_metadata", "is_ocr_source", "merge_metadata", "slim_metadata_for_downstream"]
