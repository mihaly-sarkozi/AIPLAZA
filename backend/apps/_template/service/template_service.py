from __future__ import annotations


class TemplateService:
    """Minimal reference service for new app modules."""

    def healthcheck(self) -> str:
        return "ok"


__all__ = ["TemplateService"]
