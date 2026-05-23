from __future__ import annotations

from pydantic import BaseModel

from apps.settings.domain.settings_state import DateFormat, TimeFormat, Timezone


class SettingsUpdateRequest(BaseModel):
    two_factor_enabled: bool | None = None
    timezone: Timezone | None = None
    date_format: DateFormat | None = None
    time_format: TimeFormat | None = None
    billing_company_name: str | None = None
    billing_tax_id: str | None = None
    billing_address_line: str | None = None
    billing_postal_code: str | None = None
    billing_city: str | None = None
    billing_region: str | None = None
    billing_country: str | None = None


class SettingsResponse(BaseModel):
    two_factor_enabled: bool
    timezone: Timezone
    date_format: DateFormat
    time_format: TimeFormat
    billing_company_name: str = ""
    billing_tax_id: str = ""
    billing_address_line: str = ""
    billing_postal_code: str = ""
    billing_city: str = ""
    billing_region: str = ""
    billing_country: str = ""


class SettingsSectionResponse(BaseModel):
    key: str
    label: str
    path: str
    permission: str
    order: int
    description: str = ""
    source: str = "core"


__all__ = ["SettingsResponse", "SettingsSectionResponse", "SettingsUpdateRequest"]
