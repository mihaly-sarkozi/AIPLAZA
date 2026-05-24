from __future__ import annotations

# backend/apps/settings/domain/settings_state.py
# Feladat: Frameworkfüggetlen settings állapotot és engedélyezett dátum/idő/időzóna literal típusokat definiál.
# Sárközi Mihály - 2026.05.24

from dataclasses import dataclass
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
class SettingsState:
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


__all__ = ["BillingCustomerType", "DateFormat", "SettingsState", "TimeFormat", "Timezone"]
