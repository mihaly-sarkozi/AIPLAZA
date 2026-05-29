from __future__ import annotations

# backend/apps/settings/service/settings_sections_service.py
# Feladat: Settings section lista szolgáltatás, contributor metaadatokkal egységesített response alakban.
# Sárközi Mihály - 2026.05.29

from collections.abc import Callable
from typing import Any


class SettingsSectionsService:
    def __init__(self, *, sections_lister: Callable[[], tuple] | Callable[[], list] | None = None) -> None:
        self._sections_lister = sections_lister

    def get_sections(self) -> list[dict[str, Any]]:
        if self._sections_lister is None:
            return []
        sections: list[dict[str, Any]] = []
        for section in self._sections_lister():
            if isinstance(section, dict):
                sections.append(section)
                continue
            sections.append(
                {
                    "key": getattr(section, "key"),
                    "label": getattr(section, "label"),
                    "path": getattr(section, "path"),
                    "permission": getattr(section, "permission"),
                    "order": getattr(section, "order"),
                    "description": getattr(section, "description", None),
                    "source": getattr(section, "source", None),
                }
            )
        return sections


__all__ = ["SettingsSectionsService"]
