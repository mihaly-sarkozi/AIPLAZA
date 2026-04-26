"""Subject / mention szöveg normalizálás mention–claim illesztéshez (DB nélkül)."""
from __future__ import annotations

from typing import Any

__all__ = ["mention_normalized_text", "norm_for_overlap"]


def norm_for_overlap(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def mention_normalized_text(mention: Any) -> str:
    for attr in ("normalized_text", "normalized_value", "text_content", "surface_text"):
        v = getattr(mention, attr, None)
        if v:
            return str(v)
    return ""
