from __future__ import annotations

# backend/apps/settings/service/billing_settings_service.py
# Feladat: Billing settings üzleti szolgáltatás a core settings integrációhoz és validator használathoz.
# Sárközi Mihály - 2026.05.29

from apps.settings.domain.settings_state import BillingSettingsState
from apps.settings.service.billing_validator import BillingSettingsUpdate, BillingSettingsValidator


class BillingSettingsService:
    def __init__(self, *, core_settings_service, validator: BillingSettingsValidator) -> None:
        self._core_settings_service = core_settings_service
        self._validator = validator

    @staticmethod
    def _coerce_billing_settings(payload: dict[str, object]) -> BillingSettingsState:
        return BillingSettingsState(
            billing_customer_type=str(payload.get("billing_customer_type", "company") or "company"),  # type: ignore[arg-type]
            billing_full_name=str(payload.get("billing_full_name", "") or ""),
            billing_company_name=str(payload.get("billing_company_name", "") or ""),
            billing_tax_id=str(payload.get("billing_tax_id", "") or ""),
            billing_address_line=str(payload.get("billing_address_line", "") or ""),
            billing_postal_code=str(payload.get("billing_postal_code", "") or ""),
            billing_city=str(payload.get("billing_city", "") or ""),
            billing_region=str(payload.get("billing_region", "") or ""),
            billing_country=str(payload.get("billing_country", "") or ""),
        )

    def get_billing_settings(self) -> BillingSettingsState:
        return self._coerce_billing_settings(self._core_settings_service.get_billing_profile())

    def normalize_update(self, payload: BillingSettingsUpdate) -> BillingSettingsUpdate:
        return self._validator.validate(payload)

    def update_billing_settings(
        self,
        *,
        payload: BillingSettingsUpdate,
        updated_by: int | None = None,
    ) -> BillingSettingsState:
        valid_payload = self.normalize_update(payload)
        state = self._core_settings_service.update_billing_profile(
            billing_customer_type=valid_payload.billing_customer_type,
            billing_full_name=valid_payload.billing_full_name,
            billing_company_name=valid_payload.billing_company_name,
            billing_tax_id=valid_payload.billing_tax_id,
            billing_address_line=valid_payload.billing_address_line,
            billing_postal_code=valid_payload.billing_postal_code,
            billing_city=valid_payload.billing_city,
            billing_region=valid_payload.billing_region,
            billing_country=valid_payload.billing_country,
            updated_by=updated_by,
        )
        return self._coerce_billing_settings(state)


__all__ = ["BillingSettingsService"]
