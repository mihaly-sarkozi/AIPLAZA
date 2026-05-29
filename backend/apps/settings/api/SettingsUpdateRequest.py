from __future__ import annotations

# backend/apps/settings/api/SettingsUpdateRequest.py
# Feladat: A settings PATCH request Pydantic sémája a /api/settings route számára.
# Sárközi Mihály - 2026.05.24

from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from apps.settings.domain.settings_state import BillingCustomerType, DateFormat, TimeFormat, Timezone


class TwoFactorSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    two_factor_enabled: StrictBool | None = None


class LocaleSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timezone: Timezone | None = None
    date_format: DateFormat | None = None
    time_format: TimeFormat | None = None


class BillingSettingsUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    billing_customer_type: BillingCustomerType | None = None
    billing_full_name: StrictStr | None = None
    billing_company_name: StrictStr | None = None
    billing_tax_id: StrictStr | None = None
    billing_address_line: StrictStr | None = None
    billing_postal_code: StrictStr | None = None
    billing_city: StrictStr | None = None
    billing_region: StrictStr | None = None
    billing_country: StrictStr | None = None


class SettingsUpdateRequest(TwoFactorSettingsUpdateRequest, LocaleSettingsUpdateRequest, BillingSettingsUpdateRequest):
    """Backward-compatible aggregate settings PATCH body."""


__all__ = [
    "BillingSettingsUpdateRequest",
    "LocaleSettingsUpdateRequest",
    "SettingsUpdateRequest",
    "TwoFactorSettingsUpdateRequest",
]
