from __future__ import annotations

# backend/apps/kb/kb_crud/ports/TrainingSummaryInterface.py
# Feladat: Tudástár tanítási összesítő (van-e tanítás, tanított karakterszám) szerződése.
# Sárközi Mihály - 2026.06.11

from typing import Protocol


class TrainingSummaryInterface(Protocol):
    def has_training(self, kb_uuid: str) -> bool:
        """Van-e legalább egy tanítási/ingest bejegyzés a tudástárban."""
        ...

    def training_char_count(self, kb_uuid: str) -> int:
        """Az összes tanított karakter száma a tudástárban."""
        ...


__all__ = ["TrainingSummaryInterface"]
