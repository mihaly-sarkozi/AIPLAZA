from __future__ import annotations

from typing import Protocol, runtime_checkable

@runtime_checkable
class CoreSettingsServicePort(Protocol):
    def get_settings_snapshot(self) -> dict[str, object]:
        ...

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        ...


@runtime_checkable
class SettingsFacadePort(Protocol):
    def get_settings(self) -> dict[str, object]:
        ...

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        ...

    def get_sections(self) -> list[dict[str, object]]:
        ...


__all__ = ["CoreSettingsServicePort", "SettingsFacadePort"]
