from __future__ import annotations

import re

_SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    """Mondathatárok mentén vágás, sorrend megtartásával."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    chunks = [s.strip() for s in _SENTENCE_SPLIT_REGEX.split(cleaned) if s and s.strip()]
    if chunks:
        return chunks
    return [cleaned]
