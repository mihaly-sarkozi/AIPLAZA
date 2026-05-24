from __future__ import annotations

# backend/apps/settings/domain/billing_countries.py
# Feladat: A settings számlázási ország- és régiópolicy közös backend definíciója.
# Sárközi Mihály - 2026.05.24

BILLING_COUNTRY_OTHER = "OTHER"

EU_COUNTRY_CODES = frozenset(
    {
        "AT",
        "BE",
        "BG",
        "CY",
        "CZ",
        "DE",
        "DK",
        "EE",
        "ES",
        "FI",
        "FR",
        "GR",
        "HR",
        "HU",
        "IE",
        "IT",
        "LT",
        "LU",
        "LV",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SE",
        "SI",
        "SK",
    }
)

EU_VAT_COUNTRY_CODES = frozenset({code if code != "GR" else "EL" for code in EU_COUNTRY_CODES})

EUROPEAN_COUNTRY_CODES = frozenset(
    {
        *EU_COUNTRY_CODES,
        "AD",
        "AL",
        "BA",
        "CH",
        "GB",
        "IS",
        "LI",
        "MC",
        "MD",
        "ME",
        "MK",
        "NO",
        "RS",
        "SM",
        "TR",
        "UA",
        "VA",
        "XK",
    }
)

REGION_REQUIRED_COUNTRY_CODES = frozenset({"CH", "ES", "GB", "IT"})

VAT_PREFIX_BY_COUNTRY_CODE = {"GR": "EL"}


def normalize_billing_country_code(value: str | None) -> str:
    return str(value or "").strip().upper().replace(" ", "_")


def normalize_eu_vat_id(value: str | None) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def vat_prefix_for_country(country_code: str) -> str:
    normalized = normalize_billing_country_code(country_code)
    return VAT_PREFIX_BY_COUNTRY_CODE.get(normalized, normalized)


def is_european_billing_country(country_code: str) -> bool:
    return normalize_billing_country_code(country_code) in EUROPEAN_COUNTRY_CODES


def is_eu_billing_country(country_code: str) -> bool:
    return normalize_billing_country_code(country_code) in EU_COUNTRY_CODES


def is_region_required(country_code: str) -> bool:
    return normalize_billing_country_code(country_code) in REGION_REQUIRED_COUNTRY_CODES


__all__ = [
    "BILLING_COUNTRY_OTHER",
    "EU_COUNTRY_CODES",
    "EUROPEAN_COUNTRY_CODES",
    "EU_VAT_COUNTRY_CODES",
    "REGION_REQUIRED_COUNTRY_CODES",
    "VAT_PREFIX_BY_COUNTRY_CODE",
    "is_eu_billing_country",
    "is_european_billing_country",
    "is_region_required",
    "normalize_billing_country_code",
    "normalize_eu_vat_id",
    "vat_prefix_for_country",
]
