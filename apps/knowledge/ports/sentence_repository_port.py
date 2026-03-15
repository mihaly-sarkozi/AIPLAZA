from __future__ import annotations

from abc import ABC, abstractmethod


class SentenceRepositoryPort(ABC):
    @abstractmethod
    def create_sentence_batch(self, kb_id: int, source_point_id: str, rows: list[dict]) -> list[dict]:
        """Mondatok mentése batch módban."""
        ...
