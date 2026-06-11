from __future__ import annotations

# backend/apps/kb/kb_understanding/config/UnderstandingConf.py
# Feladat: Megértési pipeline beállításai (chunking limitek, batch méretek).
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass


@dataclass(frozen=True)
class UnderstandingConfig:
    # Chunking.
    chunk_max_chars: int = 1800
    chunk_min_chars: int = 200
    chunk_overlap_chars: int = 200
    # Becsült token = karakter / token_chars_ratio.
    token_chars_ratio: float = 4.0
    # Entity / enrichment LLM hívás chunk-batch mérete.
    llm_chunk_batch_size: int = 8
    # Egy LLM hívásban feldolgozott maximális karakterszám.
    llm_max_input_chars: int = 12000


DEFAULT_UNDERSTANDING_CONFIG = UnderstandingConfig()

__all__ = ["DEFAULT_UNDERSTANDING_CONFIG", "UnderstandingConfig"]
