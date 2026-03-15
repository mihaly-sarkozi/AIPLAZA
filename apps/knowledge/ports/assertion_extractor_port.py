from __future__ import annotations

from abc import ABC, abstractmethod


class AssertionExtractorPort(ABC):
    @abstractmethod
    async def extract(self, sanitized_text: str, title: str | None = None) -> dict:
        """Sanitized szövegből strukturált assertion kinyerés."""
        ...
