from __future__ import annotations

# backend/apps/kb/kb_ingest/config/TrainingConf.py
# Feladat: Tanítási modul konfigurációs értékei (validációs limitek).
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingConfig:
    max_title_length: int = 200
    max_text_chars: int = 2_000_000


DEFAULT_TRAINING_CONFIG = TrainingConfig()

__all__ = ["DEFAULT_TRAINING_CONFIG", "TrainingConfig"]
