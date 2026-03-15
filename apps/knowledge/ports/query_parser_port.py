from __future__ import annotations

from abc import ABC, abstractmethod


class QueryParserPort(ABC):
    @abstractmethod
    def parse(self, question: str) -> dict:
        """Kérdés parse entitás/idő/hely/intent mezőkre."""
        ...
