from __future__ import annotations

# backend/apps/kb/kb_reading/dto/FileEstimateCommand.py
# Feladat: Fájl becslés parancs.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass
from typing import Any

from apps.kb.kb_reading.storage.ReadableUpload import ReadableUpload


@dataclass(frozen=True)
class FileEstimateCommand:
    """Fájl becslés parancs a bérlővel és feltöltésekkel."""

    tenant: Any
    uploads: list[ReadableUpload]


__all__ = ["FileEstimateCommand"]
