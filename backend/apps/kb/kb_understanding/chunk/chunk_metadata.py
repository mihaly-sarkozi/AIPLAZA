from __future__ import annotations

from typing import Any


def build_uniform_chunk_metadata(
    *,
    source_part_ids: list[str],
    source_normalized_part_ids: list[str],
    page_numbers: list[int],
    document_orders: list[int],
    section_title: str | None,
    heading_path: list[str],
    heading_levels: list[int],
    block_kinds: list[str],
    table_refs: list[dict[str, Any]] | None = None,
    bbox_refs: list[dict[str, Any]] | None = None,
    style_names: list[str] | None = None,
    is_from_ocr: bool = False,
    ocr_confidence: float | None = None,
    split_index: int | None = None,
    split_count: int | None = None,
    parent_chunk_id: str | None = None,
    parent_chunk_hash: str | None = None,
    page_numbers_scope: str | None = None,
    language_hints: list[str] | None = None,
    language_sources: list[str] | None = None,
    ocr_languages: list[str] | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source_part_ids": list(source_part_ids),
        "source_normalized_part_ids": list(source_normalized_part_ids),
        "page_numbers": list(page_numbers),
        "document_orders": list(document_orders),
        "section_title": section_title,
        "heading_path": list(heading_path or []),
        "heading_levels": list(heading_levels or []),
        "block_kinds": list(block_kinds or []),
        "table_refs": list(table_refs or []),
        "bbox_refs": list(bbox_refs or []),
        "style_names": list(style_names or []),
        "is_from_ocr": bool(is_from_ocr),
        "ocr_confidence": ocr_confidence,
    }
    if split_count and split_count > 1:
        metadata["split_index"] = int(split_index or 1)
        metadata["split_count"] = int(split_count)
        metadata["parent_chunk_id"] = parent_chunk_id
        metadata["parent_chunk_hash"] = parent_chunk_hash
        metadata["page_numbers_scope"] = page_numbers_scope or "parent_logical_chunk"
    if language_hints:
        metadata["language_hints"] = list(dict.fromkeys(language_hints))
    if language_sources:
        metadata["language_sources"] = list(dict.fromkeys(language_sources))
    if ocr_languages:
        metadata["ocr_languages"] = list(dict.fromkeys(ocr_languages))
    return metadata


__all__ = ["build_uniform_chunk_metadata"]
