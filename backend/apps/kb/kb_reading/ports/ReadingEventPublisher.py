from __future__ import annotations

# backend/apps/kb/kb_reading/ports/ReadingEventPublisher.py
# Feladat: Esemény kibocsátó a beolvasás után.
# Sárközi Mihály - 2026.06.07

from typing import Any, Protocol


class ReadingEventPublisher(Protocol):
    """Szerződés esemény kibocsátáshoz."""
    """Közli, hogy nyers anyag beolvasásra került."""
    def publish_material_read(
        self,
        *,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        raw_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...

    """Kéri a további feldolgozást az elfogadott elemre."""
    def publish_understanding_requested(
        self,
        *,
        knowledge_base_id: str,
        read_run_id: str,
        read_item_id: str,
        raw_ref: str,
        metadata: dict[str, Any] | None = None,
    ) -> None: ...


__all__ = ["ReadingEventPublisher"]
