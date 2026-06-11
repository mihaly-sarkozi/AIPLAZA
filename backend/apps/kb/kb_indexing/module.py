from __future__ import annotations

# backend/apps/kb/kb_indexing/module.py
# Feladat: Az indexelési modul bekötése — index-építő service-ek és repository-k.
# Skeleton: a tényleges regisztráció a full-text / vector index megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbIndexingModule:
    name = "kb.indexing"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbIndexingModule"]
