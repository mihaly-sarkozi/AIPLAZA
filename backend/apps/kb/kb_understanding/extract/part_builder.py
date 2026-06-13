from __future__ import annotations

from typing import Any

from apps.kb.kb_understanding.dto.ExtractPartDto import ExtractPart
from apps.kb.kb_understanding.enums.ExtractPartType import ExtractPartType


def table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    if not headers and not rows:
        return ""
    header_row = headers or (rows[0] if rows else [])
    body_rows = rows if headers else rows[1:]
    if not header_row:
        return "\n".join(" | ".join(row) for row in body_rows)
    lines = [
        "| " + " | ".join(header_row) + " |",
        "| " + " | ".join("---" for _ in header_row) + " |",
    ]
    for row in body_rows:
        padded = row + [""] * max(0, len(header_row) - len(row))
        lines.append("| " + " | ".join(padded[: len(header_row)]) + " |")
    return "\n".join(lines)


def table_to_plain_text(headers: list[str], rows: list[list[str]]) -> str:
    lines: list[str] = []
    if headers:
        lines.append("\t".join(headers))
    for row in rows:
        lines.append("\t".join(row))
    return "\n".join(lines)


def build_table_part(
    *,
    page_number: int | None,
    part_index: int,
    headers: list[str],
    rows: list[list[str]],
    source: str,
    metadata: dict[str, Any] | None = None,
) -> ExtractPart:
    markdown = table_to_markdown(headers, rows)
    plain = table_to_plain_text(headers, rows)
    text = markdown or plain
    return ExtractPart(
        part_type=ExtractPartType.TABLE.value,
        page_number=page_number,
        part_index=part_index,
        text=text,
        raw_payload={
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers) if headers else (len(rows[0]) if rows else 0),
            "plain_text": plain,
            "source": source,
        },
        char_count=len(text),
        metadata={"source": source, **(metadata or {})},
    )


def build_text_part(
    *,
    page_number: int | None,
    part_index: int,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> ExtractPart:
    return ExtractPart(
        part_type=ExtractPartType.TEXT.value,
        page_number=page_number,
        part_index=part_index,
        text=text,
        char_count=len(text),
        metadata=dict(metadata or {}),
    )


def summarize_parts(parts: list[ExtractPart]) -> int:
    return sum(part.char_count for part in parts)


__all__ = [
    "build_table_part",
    "build_text_part",
    "summarize_parts",
    "table_to_markdown",
    "table_to_plain_text",
]
