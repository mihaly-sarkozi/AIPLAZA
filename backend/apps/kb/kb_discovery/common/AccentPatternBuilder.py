from __future__ import annotations

import re
import unicodedata

_ACCENT_VARIANTS: dict[str, str] = {
    "a": "aáÁA",
    "e": "eéÉE",
    "i": "iíÍI",
    "o": "oóöőÓÖŐO",
    "u": "uúüűÚÜŰU",
}


def accent_insensitive_pattern(text: str) -> re.Pattern[str]:
    body = accent_insensitive_fragment(text)
    return re.compile(rf"\b{body}\b", re.IGNORECASE)


def accent_insensitive_fragment(text: str) -> str:
    parts: list[str] = []
    for char in text:
        if char.isalpha():
            base = (
                unicodedata.normalize("NFKD", char)
                .encode("ascii", "ignore")
                .decode("ascii")
                .lower()
            )
            variants = _ACCENT_VARIANTS.get(base)
            if variants:
                parts.append(f"[{variants}]")
            else:
                parts.append(re.escape(char))
        elif char.isspace():
            parts.append(r"\s+")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


__all__ = ["accent_insensitive_fragment", "accent_insensitive_pattern"]
