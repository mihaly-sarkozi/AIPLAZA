from __future__ import annotations

# backend/apps/kb/kb_understanding/config/UnderstandingConf.py
# Feladat: Megértési pipeline beállításai (chunking limitek).
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderstandingConfig:
    chunk_max_chars: int = 1800
    chunk_min_chars: int = 200
    chunk_overlap_chars: int = 200
    token_chars_ratio: float = 4.0
    normalize_batch_size: int = 100
    chunk_insert_batch_size: int = 100


DEFAULT_UNDERSTANDING_CONFIG = UnderstandingConfig()

__all__ = ["DEFAULT_UNDERSTANDING_CONFIG", "UnderstandingConfig"]
