from __future__ import annotations

# backend/apps/kb/kb_ingest/dto/FileEstimateCommand.py
# Feladat: Fájl becslés parancs.
# (Átemelve a megszüntetett kb_reading modulból.)
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass
from typing import Any

from apps.kb.kb_ingest.ports.ReadableUpload import ReadableUpload


@dataclass(frozen=True)
class FileEstimateCommand:
    """Fájl becslés parancs a bérlővel és feltöltésekkel."""

    tenant: Any
    uploads: list[ReadableUpload]


__all__ = ["FileEstimateCommand"]
