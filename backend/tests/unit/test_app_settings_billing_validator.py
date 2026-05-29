# backend/tests/unit/test_app_settings_billing_validator.py
# Feladat: BillingSettingsValidator company/private validációs szabályainak unit tesztje.
# Sárközi Mihály - 2026.05.29

from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.settings.service.billing_validator import BillingSettingsUpdate, BillingSettingsValidator
from apps.settings.service.eu_vat_validation_service import EuVatValidationResult

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _VatValidator:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid

    def validate(self, *, country_code: str, vat_id: str) -> EuVatValidationResult:
        return EuVatValidationResult(country_code=country_code, vat_number=vat_id, valid=self.valid)


def test_validator_accepts_valid_company_payload() -> None:
    validator = BillingSettingsValidator(eu_vat_validation_service=_VatValidator(valid=True))
    payload = validator.validate(
        BillingSettingsUpdate(
            billing_customer_type="company",
            billing_company_name="Acme Kft.",
            billing_tax_id="HU12345678",
            billing_country="HU",
            billing_postal_code="1111",
            billing_city="Budapest",
            billing_address_line="Fo utca 1.",
        )
    )
    assert payload.billing_customer_type == "company"
    assert payload.billing_tax_id == "HU12345678"


def test_validator_accepts_valid_private_payload() -> None:
    validator = BillingSettingsValidator()
    payload = validator.validate(
        BillingSettingsUpdate(
            billing_customer_type="private",
            billing_full_name="Teszt Elek",
            billing_country="CH",
            billing_region="ZH",
            billing_postal_code="8000",
            billing_city="Zurich",
            billing_address_line="Main street 1.",
        )
    )
    assert payload.billing_customer_type == "private"
    assert payload.billing_company_name == ""


def test_validator_rejects_missing_required_fields() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="private",
                billing_full_name="Teszt Elek",
                billing_country="HU",
                billing_city="Budapest",
            )
        )
    assert exc.value.status_code == 422


def test_validator_rejects_invalid_country() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="private",
                billing_full_name="Teszt Elek",
                billing_country="OTHER",
                billing_postal_code="1111",
                billing_city="Budapest",
                billing_address_line="Fo utca 1.",
            )
        )
    assert exc.value.status_code == 422


def test_validator_rejects_invalid_vat() -> None:
    validator = BillingSettingsValidator(eu_vat_validation_service=_VatValidator(valid=False))
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="company",
                billing_company_name="Acme Kft.",
                billing_tax_id="HU12345678",
                billing_country="HU",
                billing_postal_code="1111",
                billing_city="Budapest",
                billing_address_line="Fo utca 1.",
            )
        )
    assert exc.value.status_code == 422


def test_validator_private_rejects_company_fields() -> None:
    validator = BillingSettingsValidator()
    with pytest.raises(HTTPException) as exc:
        validator.validate(
            BillingSettingsUpdate(
                billing_customer_type="private",
                billing_full_name="Teszt Elek",
                billing_company_name="Acme Kft.",
                billing_country="HU",
                billing_postal_code="1111",
                billing_city="Budapest",
                billing_address_line="Fo utca 1.",
            )
        )
    assert exc.value.status_code == 422
