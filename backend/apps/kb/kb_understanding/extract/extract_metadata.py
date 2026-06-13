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


def slim_metadata_for_downstream(metadata: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source",
        "document_order",
        "page_number",
        "part_index",
        "block_kind",
        "style_name",
        "style_id",
        "heading_level",
        "is_heading",
        "is_list",
        "list_level",
        "numbering_id",
        "numbering_level",
        "bbox",
        "font_names",
        "font_sizes",
        "is_bold_guess",
        "is_heading_guess",
        "header_footer_confidence",
        "table_index",
        "row_count",
        "column_count",
        "headers",
        "rows",
        "ocr_engine",
        "ocr_language",
        "ocr_confidence",
        "layout_order",
        "section_index",
    )
    slim: dict[str, Any] = {}
    for key in keys:
        if key in metadata:
            slim[key] = metadata[key]
    style = metadata.get("style")
    if isinstance(style, dict):
        for nested_key in ("style_name", "style_id", "heading_level"):
            if nested_key in style and nested_key not in slim:
                slim[nested_key] = style[nested_key]
    layout = metadata.get("layout")
    if isinstance(layout, dict):
        for nested_key in ("bbox", "layout_order", "header_footer_confidence"):
            if nested_key in layout and nested_key not in slim:
                slim[nested_key] = layout[nested_key]
    return slim


__all__ = ["build_base_metadata", "merge_metadata", "slim_metadata_for_downstream"]
