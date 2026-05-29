from __future__ import annotations

# backend/apps/settings/domain/settings_state.py
# Feladat: Frameworkfüggetlen settings állapotot és engedélyezett dátum/idő/időzóna literal típusokat definiál.
# Sárközi Mihály - 2026.05.24

from dataclasses import asdict, dataclass
from typing import Any
from typing import Literal

DateFormat = Literal["YYYY-MM-DD", "DD.MM.YYYY", "DD/MM/YYYY", "MM/DD/YYYY"]
TimeFormat = Literal["HH:mm", "HH:mm:ss", "hh:mm A"]
BillingCustomerType = Literal["company", "private"]
Timezone = Literal[
    "UTC",
    "Europe/London",
    "Europe/Paris",
    "Europe/Berlin",
    "Europe/Madrid",
    "Europe/Rome",
    "Europe/Amsterdam",
    "Europe/Zurich",
    "Europe/Vienna",
    "Europe/Prague",
    "Europe/Warsaw",
    "Europe/Budapest",
    "Europe/Athens",
    "Europe/Bucharest",
    "Europe/Istanbul",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Singapore",
    "Asia/Hong_Kong",
    "Asia/Shanghai",
    "Asia/Seoul",
    "Asia/Tokyo",
    "Australia/Sydney",
    "America/Toronto",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Mexico_City",
    "America/Sao_Paulo",
    "Africa/Cairo",
    "Africa/Johannesburg",
]


@dataclass(frozen=True)
class TwoFactorSettingsState:
    two_factor_enabled: bool = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.model_dump() == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self):
        return asdict(self).keys()

    def items(self):
        return asdict(self).items()

    def values(self):
        return asdict(self).values()

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class LocaleSettingsState:
    timezone: Timezone = "UTC"
    date_format: DateFormat = "YYYY-MM-DD"
    time_format: TimeFormat = "HH:mm"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.model_dump() == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self):
        return asdict(self).keys()

    def items(self):
        return asdict(self).items()

    def values(self):
        return asdict(self).values()

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BillingSettingsState:
    billing_customer_type: BillingCustomerType = "company"
    billing_full_name: str = ""
    billing_company_name: str = ""
    billing_tax_id: str = ""
    billing_address_line: str = ""
    billing_postal_code: str = ""
    billing_city: str = ""
    billing_region: str = ""
    billing_country: str = ""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.model_dump() == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self):
        return asdict(self).keys()

    def items(self):
        return asdict(self).items()

    def values(self):
        return asdict(self).values()

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SettingsState:
    """Backward-compatible aggregate settings response."""

    two_factor_enabled: bool = False
    timezone: Timezone = "UTC"
    date_format: DateFormat = "YYYY-MM-DD"
    time_format: TimeFormat = "HH:mm"
    billing_customer_type: BillingCustomerType = "company"
    billing_full_name: str = ""
    billing_company_name: str = ""
    billing_tax_id: str = ""
    billing_address_line: str = ""
    billing_postal_code: str = ""
    billing_city: str = ""
    billing_region: str = ""
    billing_country: str = ""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, dict):
            return self.model_dump() == other
        return super().__eq__(other)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def keys(self):
        return asdict(self).keys()

    def items(self):
        return asdict(self).items()

    def values(self):
        return asdict(self).values()

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "BillingCustomerType",
    "BillingSettingsState",
    "DateFormat",
    "LocaleSettingsState",
    "SettingsState",
    "TimeFormat",
    "Timezone",
    "TwoFactorSettingsState",
]
