from __future__ import annotations

from typing import Protocol


class VectorStoreAdapter(Protocol):
    async def upsert(self, *, collection: str, vectors: list[dict]) -> int: ...
