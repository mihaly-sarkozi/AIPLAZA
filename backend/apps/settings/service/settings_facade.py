from __future__ import annotations

from collections.abc import Callable

from apps.settings.domain.settings_state import SettingsState
from apps.settings.mappers.settings_mapper import (
    build_settings_response,
    build_settings_section_response,
)
from apps.settings.service.ports import CoreSettingsServicePort


class SettingsFacade:
    DEFAULT_STATE = SettingsState()

    def __init__(
        self,
        *,
        core_settings_service: CoreSettingsServicePort,
        sections_lister: Callable[[], tuple] | Callable[[], list] | None = None,
    ) -> None:
        self._core_settings_service = core_settings_service
        self._sections_lister = sections_lister

    @staticmethod
    def _coerce_state(payload: dict[str, object]) -> SettingsState:
        return SettingsState(
            two_factor_enabled=bool(payload.get("two_factor_enabled", False)),
            timezone=str(payload.get("timezone", SettingsFacade.DEFAULT_STATE.timezone) or SettingsFacade.DEFAULT_STATE.timezone),  # type: ignore[arg-type]
            date_format=str(payload.get("date_format", SettingsFacade.DEFAULT_STATE.date_format) or SettingsFacade.DEFAULT_STATE.date_format),  # type: ignore[arg-type]
            time_format=str(payload.get("time_format", SettingsFacade.DEFAULT_STATE.time_format) or SettingsFacade.DEFAULT_STATE.time_format),  # type: ignore[arg-type]
        )

    def get_settings(self) -> dict[str, object]:
        return build_settings_response(self._coerce_state(self._core_settings_service.get_settings_snapshot()))

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        state = self._core_settings_service.update_settings(
            two_factor_enabled=two_factor_enabled,
            timezone=timezone,
            date_format=date_format,
            time_format=time_format,
            updated_by=updated_by,
        )
        return build_settings_response(self._coerce_state(state))

    def get_sections(self) -> list[dict[str, object]]:
        if self._sections_lister is None:
            return []
        return [build_settings_section_response(section) for section in self._sections_lister()]


__all__ = ["SettingsFacade"]
