from __future__ import annotations

# backend/apps/kb/kb_feedback/module.py
# Feladat: A visszajelzési modul bekötése — feedback gyűjtő service-ek és router.
# Skeleton: a tényleges regisztráció a feedback gyűjtés megvalósításakor kerül be.
# Sárközi Mihály - 2026.06.11


class KbFeedbackModule:
    name = "kb.feedback"

    def register_routes(self, app) -> None:
        pass

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbFeedbackModule"]
