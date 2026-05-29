from __future__ import annotations

# backend/apps/settings/service/locale_settings_service.py
# Feladat: Locale settings (timezone/date/time format) üzleti szolgáltatás a core settings réteghez.
# Sárközi Mihály - 2026.05.29

from dataclasses import dataclass

from apps.settings.domain.settings_state import LocaleSettingsState, SettingsState


@dataclass(frozen=True)
class LocaleSettingsUpdate:
    timezone: str | None = None
    date_format: str | None = None
    time_format: str | None = None


class LocaleSettingsService:
    def __init__(self, *, core_settings_service) -> None:
        self._core_settings_service = core_settings_service

    @staticmethod
    def _coerce_locale_settings(payload: dict[str, object]) -> LocaleSettingsState:
        return LocaleSettingsState(
            timezone=str(payload.get("timezone", SettingsState().timezone) or SettingsState().timezone),  # type: ignore[arg-type]
            date_format=str(payload.get("date_format", SettingsState().date_format) or SettingsState().date_format),  # type: ignore[arg-type]
            time_format=str(payload.get("time_format", SettingsState().time_format) or SettingsState().time_format),  # type: ignore[arg-type]
        )

    def get_locale_settings(self) -> LocaleSettingsState:
        return self._coerce_locale_settings(self._core_settings_service.get_locale_settings())

    def update_locale_settings(self, *, payload: LocaleSettingsUpdate, updated_by: int | None = None) -> LocaleSettingsState:
        state = self._core_settings_service.update_locale_settings(
            timezone=payload.timezone,
            date_format=payload.date_format,
            time_format=payload.time_format,
            updated_by=updated_by,
        )
        return self._coerce_locale_settings(state)


__all__ = ["LocaleSettingsService", "LocaleSettingsUpdate"]
