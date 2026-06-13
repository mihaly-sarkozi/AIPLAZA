from __future__ import annotations

import re

_SENTENCE = re.compile(r"[^.!?]+[.!?]?")
_PREVIEW_LIMIT = 280


def lead_sentence(text: str) -> str:
    match = _SENTENCE.search(text.strip())
    return (match.group(0).strip() if match else text.strip())[:500]


def preview_text(text: str, *, limit: int = _PREVIEW_LIMIT) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


__all__ = ["lead_sentence", "preview_text"]
