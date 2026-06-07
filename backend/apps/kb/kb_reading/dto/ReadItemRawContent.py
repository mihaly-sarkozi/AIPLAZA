from __future__ import annotations

# backend/apps/kb/kb_reading/dto/ReadItemRawContent.py
# Feladat: ReadItemRawContent válasz séma.
# Sárközi Mihály - 2026.06.07
from pydantic import BaseModel, Field

class ReadItemRawContent(BaseModel):
    """Válasz séma az elem nyers tartalmához."""
    body: bytes
    media_type: str
    filename: str

__all__ = ['ReadItemRawContent']
