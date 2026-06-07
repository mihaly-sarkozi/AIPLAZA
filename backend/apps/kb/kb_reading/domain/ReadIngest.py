from __future__ import annotations

# backend/apps/kb/kb_reading/domain/ReadIngest.py
# Feladat: Egy beolvasás logikai egysége (run + item pár).
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass

from apps.kb.kb_reading.domain.ReadItem import ReadItem
from apps.kb.kb_reading.domain.ReadRun import ReadRun


@dataclass
class ReadIngest:
    """Egy beolvasás: fájl vagy URL.

    Logikailag egy egység. A perzisztencia két sort használ (run fejléc + item),
    de a service ettől függetlenül egy ``ReadIngest``-tel dolgozik.
    """

    run: ReadRun
    item: ReadItem

    @property
    def run_id(self) -> str:
        return self.run.id

    @property
    def item_id(self) -> str:
        return self.item.id


__all__ = ["ReadIngest"]
