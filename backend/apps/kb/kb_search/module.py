from __future__ import annotations

# backend/apps/kb/kb_search/module.py
# Feladat: A keresési modul bekötése — kereső service-ek és router.
# Skeleton: a tényleges regisztráció a hybrid search megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbSearchModule:
    name = "kb.search"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbSearchModule"]
