from __future__ import annotations

from typing import Any

from shared.documents.text_extraction import extract_text_from_upload
from shared.text.chunking import chunk_text_for_training


def build_sentence_rows(chunks: list[str], title: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    safe_title = (title or "").strip()
    for i, chunk in enumerate(chunks):
        rows.append(
            {
                "text": chunk,
                "payload": {
                    "source": "user_training",
                    "title": safe_title,
                    "chunk_index": i,
                },
            }
        )
    return rows


__all__ = [
    "build_sentence_rows",
    "chunk_text_for_training",
    "extract_text_from_upload",
]
