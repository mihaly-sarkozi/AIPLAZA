from __future__ import annotations

from typing import NewType

TenantId = NewType("TenantId", str)
UserId = NewType("UserId", str)
KnowledgeBaseId = NewType("KnowledgeBaseId", str)
SourceId = NewType("SourceId", str)
MaterialId = NewType("MaterialId", str)
RunId = NewType("RunId", str)
ChunkId = NewType("ChunkId", str)
SearchRunId = NewType("SearchRunId", str)
FeedbackId = NewType("FeedbackId", str)

__all__ = [
    "ChunkId",
    "FeedbackId",
    "KnowledgeBaseId",
    "MaterialId",
    "RunId",
    "SearchRunId",
    "SourceId",
    "TenantId",
    "UserId",
]
