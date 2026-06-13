from __future__ import annotations

from enum import Enum


class ProcessingModule(str, Enum):
    KB_INGEST = "kb_ingest"
    KB_UNDERSTANDING = "kb_understanding"
    KB_DISCOVERY = "kb_discovery"
    KB_EMBEDDING = "kb_embedding"
    KB_INDEXING = "kb_indexing"
    KB_SEARCH = "kb_search"


__all__ = ["ProcessingModule"]
