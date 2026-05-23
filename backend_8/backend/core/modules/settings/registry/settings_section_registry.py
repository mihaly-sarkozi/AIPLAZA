# backend/core/modules/settings/registry/settings_section_registry.py
# Feladat: A settings UI section registry típusait és globális registry példányát tartalmazza. Core és app modulok SettingsSection rekordokat regisztrálhatnak, amelyeket a settings app rendezve listáz a felületi navigációhoz. Integrációs contract réteg settings felület bővítéséhez.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SettingsSection:
    key: str
    label: str
    path: str
    permission: str
    order: int = 100
    description: str = ""
    source: str = "core"


class SettingsSectionContributor(Protocol):
    def to_settings_section(self) -> SettingsSection:
        ...


class SettingsSectionRegistry:
    def __init__(self) -> None:
        self._sections: dict[str, SettingsSection] = {}

    def register(self, section: SettingsSection) -> None:
        key = (section.key or "").strip()
        if not key:
            raise ValueError("settings section key must not be empty")
        self._sections[key] = section

    def list(self) -> tuple[SettingsSection, ...]:
        return tuple(sorted(self._sections.values(), key=lambda item: (item.order, item.key)))

    def clear(self) -> None:
        self._sections.clear()


_registry = SettingsSectionRegistry()


def register_settings_section(section: SettingsSection) -> None:
    _registry.register(section)


def list_settings_sections() -> tuple[SettingsSection, ...]:
    return _registry.list()


def clear_settings_sections() -> None:
    _registry.clear()


__all__ = [
    "SettingsSection",
    "SettingsSectionContributor",
    "SettingsSectionRegistry",
    "clear_settings_sections",
    "list_settings_sections",
    "register_settings_section",
]

