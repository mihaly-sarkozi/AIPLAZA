from __future__ import annotations


class KbMaintenanceModule:
    name = "kb.maintenance"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        pass

    def register_event_handlers(self, event_bus) -> None:
        pass


__all__ = ["KbMaintenanceModule"]
