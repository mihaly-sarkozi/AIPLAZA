from __future__ import annotations

# backend/apps/kb/kb_maintenance/module.py
# Feladat: A karbantartási modul bekötése — újraindexelés, retry, cleanup service-ek.
# Skeleton: a tényleges regisztráció a karbantartási folyamatok megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbMaintenanceModule:
    name = "kb.maintenance"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbMaintenanceModule"]
