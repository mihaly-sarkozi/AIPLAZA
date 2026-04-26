from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalProfile:
    key: str = "basic_retrieval_v1"
    top_k: int = 5
    rerank: bool = False
    score_threshold: float | None = None
    duplicate_collapse: bool = True
    source_grouping: str = "source"


DEFAULT_RETRIEVAL_PROFILE = RetrievalProfile()


__all__ = ["DEFAULT_RETRIEVAL_PROFILE", "RetrievalProfile"]
