from __future__ import annotations

from typing import Protocol

from apps.kb.shared.contracts import ChunkLanguageUpdate


class ChunkLanguageWriterPort(Protocol):
    def bulk_update_chunk_language(self, results: list[ChunkLanguageUpdate]) -> int: ...


__all__ = ["ChunkLanguageWriterPort"]
