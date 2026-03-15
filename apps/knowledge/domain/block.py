from __future__ import annotations

from pydantic import BaseModel


class Block(BaseModel):
    """Dokumentum-blokk (ingestion egység), amelyből mondat/chunk/assertion készül."""

    source_point_id: str
    block_order: int = 0
    text: str
    token_count: int = 0
