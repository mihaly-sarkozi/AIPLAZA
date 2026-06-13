from __future__ import annotations

from enum import Enum


class ProcessingStage(str, Enum):
    EXTRACT = "EXTRACT"
    NORMALIZE = "NORMALIZE"
    CHUNKING = "CHUNKING"
    VALIDATION = "VALIDATION"
    DISCOVERY = "DISCOVERY"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    INGEST = "INGEST"


__all__ = ["ProcessingStage"]
