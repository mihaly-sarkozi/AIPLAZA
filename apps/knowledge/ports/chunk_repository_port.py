from __future__ import annotations

from abc import ABC, abstractmethod


class ChunkRepositoryPort(ABC):
    @abstractmethod
    def create_structural_chunk_batch(self, kb_id: int, source_point_id: str, rows: list[dict]) -> list[dict]:
        """Chunk rekordok mentése batch módban."""
        ...
