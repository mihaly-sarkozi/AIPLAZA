from __future__ import annotations

# backend/apps/settings/service/billing_validator.py
# Feladat: A settings billing adatok üzleti validációja és normalizálása külön szolgáltatásként.
# Sárközi Mihály - 2026.05.29

from dataclasses import dataclass

from fastapi import HTTPException

from apps.settings.domain.billing_countries import (
    BILLING_COUNTRY_OTHER,
    is_eu_billing_country,
    is_european_billing_country,
    normalize_billing_country_code,
    normalize_eu_vat_id,
)
from apps.settings.service.eu_vat_validation_service import EuVatValidationService, EuVatValidationUnavailableError


@dataclass(frozen=True)
class BillingSettingsUpdate:
    billing_customer_type: str | None = None
    billing_full_name: str | None = None
    billing_company_name: str | None = None
    billing_tax_id: str | None = None
    billing_address_line: str | None = None
    billing_postal_code: str | None = None
    billing_city: str | None = None
    billing_region: str | None = None
    billing_country: str | None = None


class BillingSettingsValidator:
    def __init__(
        self,
        *,
        eu_vat_validation_service: EuVatValidationService | None = None,
        require_eu_vat_validation: bool = True,
    ) -> None:
        self._eu_vat_validation_service = eu_vat_validation_service or EuVatValidationService()
        self._require_eu_vat_validation = require_eu_vat_validation

    def validate(self, payload: BillingSettingsUpdate) -> BillingSettingsUpdate:
        customer_type = (payload.billing_customer_type or "").strip() or "company"
        if customer_type not in {"company", "private"}:
            raise HTTPException(status_code=422, detail="Invalid billing customer type.")
        country = normalize_billing_country_code(payload.billing_country)
        if not country or country == BILLING_COUNTRY_OTHER or not is_european_billing_country(country):
            raise HTTPException(status_code=422, detail="The service currently operates only in Europe.")

        required = {
            "billing_country": country,
            "billing_postal_code": payload.billing_postal_code,
            "billing_city": payload.billing_city,
            "billing_address_line": payload.billing_address_line,
        }
        missing = [key for key, value in required.items() if not str(value or "").strip()]
        billing_full_name = payload.billing_full_name
        billing_company_name = payload.billing_company_name
        billing_tax_id = payload.billing_tax_id
        if customer_type == "company":
            if not is_eu_billing_country(country):
                raise HTTPException(status_code=422, detail="Company billing is currently available only for EU countries.")
            required_company = {
                "billing_company_name": billing_company_name,
                "billing_tax_id": billing_tax_id,
            }
            missing.extend(key for key, value in required_company.items() if not str(value or "").strip())
            if missing:
                raise HTTPException(status_code=422, detail="All company billing fields are required.")
            normalized_vat = normalize_eu_vat_id(billing_tax_id)
            if self._require_eu_vat_validation:
                try:
                    result = self._eu_vat_validation_service.validate(country_code=country, vat_id=normalized_vat)
                except EuVatValidationUnavailableError as exc:
                    raise HTTPException(status_code=503, detail="EU VAT validation is temporarily unavailable.") from exc
                if not result.valid:
                    raise HTTPException(status_code=422, detail="Invalid EU VAT number.")
            billing_tax_id = normalized_vat
            billing_full_name = (billing_full_name or "").strip()
        else:
            required_private = {"billing_full_name": billing_full_name}
            missing.extend(key for key, value in required_private.items() if not str(value or "").strip())
            if str(billing_company_name or "").strip() or str(billing_tax_id or "").strip():
                raise HTTPException(status_code=422, detail="Private billing must not include company name or VAT number.")
            if missing:
                raise HTTPException(status_code=422, detail="All private billing fields are required.")
            billing_company_name = ""
            billing_tax_id = ""

        return BillingSettingsUpdate(
            billing_customer_type=customer_type,
            billing_full_name=(billing_full_name or "").strip(),
            billing_company_name=(billing_company_name or "").strip(),
            billing_tax_id=(billing_tax_id or "").strip(),
            billing_address_line=(payload.billing_address_line or "").strip(),
            billing_postal_code=(payload.billing_postal_code or "").strip(),
            billing_city=(payload.billing_city or "").strip(),
            billing_region=payload.billing_region.strip() if isinstance(payload.billing_region, str) else payload.billing_region,
            billing_country=country,
        )


__all__ = ["BillingSettingsUpdate", "BillingSettingsValidator"]
