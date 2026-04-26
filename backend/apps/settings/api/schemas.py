from __future__ import annotations

from pydantic import BaseModel

from apps.settings.domain.settings_state import DateFormat, TimeFormat, Timezone


class SettingsUpdateRequest(BaseModel):
    two_factor_enabled: bool | None = None
    timezone: Timezone | None = None
    date_format: DateFormat | None = None
    time_format: TimeFormat | None = None


class SettingsResponse(BaseModel):
    two_factor_enabled: bool
    timezone: Timezone
    date_format: DateFormat
    time_format: TimeFormat


class SettingsSectionResponse(BaseModel):
    key: str
    label: str
    path: str
    permission: str
    order: int
    description: str = ""
    source: str = "core"


__all__ = ["SettingsResponse", "SettingsSectionResponse", "SettingsUpdateRequest"]
