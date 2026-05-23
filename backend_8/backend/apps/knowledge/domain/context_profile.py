from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContextProfile:
    key: str = "chat_context_v1"
    max_context_chars: int = 4000
    max_chunks: int = 6
    deduplicate: bool = True
    citation_limit: int = 6
    ordering: str = "score_desc"


DEFAULT_CONTEXT_PROFILE = ContextProfile()


__all__ = ["ContextProfile", "DEFAULT_CONTEXT_PROFILE"]
