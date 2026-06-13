from __future__ import annotations

import re


class ChecklistExtractor:
    _ITEM = re.compile(r"^\s*(?:[-*]|\[\s?\])\s+(.+)$", re.MULTILINE)

    def extract(self, text: str) -> list[str]:
        return [item.strip() for item in self._ITEM.findall(text)]


__all__ = ["ChecklistExtractor"]
