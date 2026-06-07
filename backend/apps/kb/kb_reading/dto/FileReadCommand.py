from __future__ import annotations

# backend/apps/kb/kb_reading/dto/FileReadCommand.py
# Feladat: FileReadCommand adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass

from apps.kb.kb_reading.storage.ReadableUpload import ReadableUpload


@dataclass(frozen=True)
class FileReadCommand:
    """Fájl beolvasás parancs a bérlővel és feltöltésekkel."""

    tenant: str
    knowledge_base_id: str
    created_by: int
    uploads: list[ReadableUpload]


__all__ = ["FileReadCommand"]
