from __future__ import annotations

# backend/apps/kb/kb_testing/module.py
# Feladat: A tudásfolyamat-minőségmérő modul bekötése.
# Skeleton: a tényleges regisztráció a minőségmérési szolgáltatások megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbTestingModule:
    name = "kb.testing"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbTestingModule"]
