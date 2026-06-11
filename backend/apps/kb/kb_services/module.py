from __future__ import annotations

# backend/apps/kb/kb_services/module.py
# Feladat: A tudásszolgáltatási modul bekötése — üzleti szolgáltatás service-ek és router.
# Skeleton: a tényleges regisztráció az első szolgáltatás (question-answer) megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbServicesModule:
    name = "kb.services"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbServicesModule"]
