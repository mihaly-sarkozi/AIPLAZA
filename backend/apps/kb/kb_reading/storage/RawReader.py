from __future__ import annotations

# backend/apps/kb/kb_reading/storage/raw_reader.py
# Feladat: Nyers anyag olvasása a tárolóból.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass
from typing import BinaryIO

from apps.kb.kb_reading.storage.ReadingStorage import ReadingStorage


@dataclass
class RawReader:
    """Nyers anyag olvasása a tárolóból."""
    storage: ReadingStorage

    def open(self, raw_ref: str) -> BinaryIO:
        """Megnyitja a nyers anyagot."""
        return self.storage.open_raw(raw_ref)

    def read_bytes(self, raw_ref: str) -> bytes:
        """Bájtokat olvas a nyers tárolóból."""
        stream = self.open(raw_ref)
        try:
            return stream.read()
        finally:
            stream.close()

    def delete(self, raw_ref: str) -> None:
        """Törli a nyers anyagot."""
        self.storage.delete_raw(raw_ref)


__all__ = ["RawReader"]
