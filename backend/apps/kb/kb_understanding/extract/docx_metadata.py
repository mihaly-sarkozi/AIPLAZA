from __future__ import annotations

import re
from typing import Any

from apps.kb.kb_understanding.extract.extract_metadata import build_base_metadata

_HEADING_STYLE = re.compile(r"^Heading\s*(\d+)$", re.IGNORECASE)
_LIST_STYLE = re.compile(r"^List\s", re.IGNORECASE)
_LIST_MARKER = re.compile(r"^(\d+[.)]|[•\-*–])\s+")


def extract_paragraph_metadata(paragraph, *, document_order: int, part_index: int, block_index: int) -> dict[str, Any]:
    style_name = paragraph.style.name if paragraph.style is not None else None
    style_id = getattr(paragraph.style, "style_id", None) if paragraph.style is not None else None
    heading_level = _heading_level(style_name)
    is_heading = heading_level is not None
    numbering = _numbering_info(paragraph)
    is_list = numbering["is_list"] or bool(style_name and _LIST_STYLE.match(style_name))
    block_kind = _paragraph_block_kind(is_heading=is_heading, is_list=is_list, style_name=style_name)
    alignment = _alignment_name(paragraph)
    runs = _extract_runs(paragraph)
    has_page_break = _has_page_break(paragraph)

    extra = {
        "style_name": style_name,
        "style_id": style_id,
        "is_heading": is_heading,
        "heading_level": heading_level,
        "is_list": is_list,
        "list_level": numbering["list_level"],
        "numbering_id": numbering["numbering_id"],
        "numbering_level": numbering["numbering_level"],
        "list_marker": numbering["list_marker"],
        "alignment": alignment,
        "runs": runs,
        "block_index": block_index,
        "has_page_break": has_page_break,
    }
    return build_base_metadata(
        source="docx_paragraph",
        document_order=document_order,
        page_number=block_index,
        part_index=part_index,
        block_kind=block_kind,
        style={
            "style_name": style_name,
            "style_id": style_id,
            "heading_level": heading_level,
            "alignment": alignment,
        },
        layout={"block_index": block_index, "has_page_break": has_page_break},
        extra=extra,
    )


def extract_table_metadata(
    table,
    *,
    document_order: int,
    part_index: int,
    block_index: int,
    table_index: int,
    headers: list[str],
    rows: list[list[str]],
    merged_cells: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    extra = {
        "row_count": len(rows),
        "column_count": len(headers) if headers else (len(rows[0]) if rows else 0),
        "headers": headers,
        "rows": rows,
        "merged_cells": merged_cells or [],
        "table_index": table_index,
        "block_index": block_index,
    }
    return build_base_metadata(
        source="docx_table",
        document_order=document_order,
        page_number=block_index,
        part_index=part_index,
        block_kind="table",
        layout={"table_index": table_index, "block_index": block_index},
        extra=extra,
    )


def extract_header_footer_metadata(
    *,
    source: str,
    text: str,
    document_order: int,
    part_index: int,
    section_index: int,
    block_kind: str,
) -> dict[str, Any]:
    return build_base_metadata(
        source=source,
        document_order=document_order,
        page_number=section_index,
        part_index=part_index,
        block_kind=block_kind,
        layout={"section_index": section_index},
        extra={"section_index": section_index, "text_preview": text[:200]},
    )


def extract_merged_cells(table) -> list[dict[str, Any]]:
    from docx.oxml.ns import qn

    merged: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.rows):
        for col_index, cell in enumerate(row.cells):
            tc = cell._tc
            grid_span_el = tc.find(qn("w:gridSpan"))
            if grid_span_el is not None:
                value = grid_span_el.get(qn("w:val"))
                if value and int(value) > 1:
                    merged.append(
                        {
                            "row": row_index,
                            "column": col_index,
                            "grid_span": int(value),
                        }
                    )
    return merged


def _paragraph_block_kind(*, is_heading: bool, is_list: bool, style_name: str | None) -> str:
    if is_heading:
        return "heading"
    if is_list:
        return "list"
    if style_name and style_name.lower() in {"header", "footer"}:
        return style_name.lower()
    return "paragraph"


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    match = _HEADING_STYLE.match(style_name.strip())
    if match:
        return int(match.group(1))
    if style_name.strip().lower() == "title":
        return 0
    return None


def _alignment_name(paragraph) -> str | None:
    alignment = getattr(paragraph, "alignment", None)
    if alignment is None:
        return None
    name = getattr(alignment, "name", None)
    return str(name).lower() if name else None


def _extract_runs(paragraph) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for run in paragraph.runs:
        text = run.text or ""
        if not text:
            continue
        font = run.font
        size = font.size.pt if font.size is not None else None
        runs.append(
            {
                "text": text,
                "bold": bool(run.bold),
                "italic": bool(run.italic),
                "underline": bool(run.underline),
                "font_name": font.name,
                "font_size": size,
            }
        )
    return runs


def _numbering_info(paragraph) -> dict[str, Any]:
    result = {
        "is_list": False,
        "list_level": None,
        "numbering_id": None,
        "numbering_level": None,
        "list_marker": None,
    }
    p_pr = paragraph._p.pPr
    if p_pr is not None and p_pr.numPr is not None:
        num_pr = p_pr.numPr
        if num_pr.ilvl is not None:
            result["list_level"] = int(num_pr.ilvl.val)
            result["numbering_level"] = str(num_pr.ilvl.val)
        if num_pr.numId is not None:
            result["numbering_id"] = str(num_pr.numId.val)
        result["is_list"] = True

    text = (paragraph.text or "").strip()
    marker_match = _LIST_MARKER.match(text)
    if marker_match:
        result["is_list"] = True
        if result["list_marker"] is None:
            result["list_marker"] = marker_match.group(1)
    return result


def _has_page_break(paragraph) -> bool:
    from docx.oxml.ns import qn

    for br in paragraph._p.findall(".//" + qn("w:br")):
        if br.get(qn("w:type")) == "page":
            return True
    return False


__all__ = [
    "extract_header_footer_metadata",
    "extract_merged_cells",
    "extract_paragraph_metadata",
    "extract_table_metadata",
]
