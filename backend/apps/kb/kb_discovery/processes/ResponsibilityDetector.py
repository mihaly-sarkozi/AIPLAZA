from __future__ import annotations

import re


class ResponsibilityDetector:
    _RESP = re.compile(
        r"\b(felelős|owner|responsible)\s*:?\s*([\wÁÉÍÓÖŐÚÜŰáéíóöőúüű .-]+)",
        re.IGNORECASE,
    )

    def detect(self, text: str) -> list[str]:
        return [match.group(2).strip() for match in self._RESP.finditer(text)]


__all__ = ["ResponsibilityDetector"]
