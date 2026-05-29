from __future__ import annotations

# backend/apps/settings/service/settings_facade.py
# Feladat: App-szintű settings orchestrator. A vékony route réteg hívásait dedikált settings service-ek felé delegálja.
# Sárközi Mihály - 2026.05.24

from collections.abc import Callable

from apps.settings.domain.settings_state import BillingSettingsState, LocaleSettingsState, SettingsState, TwoFactorSettingsState
from apps.settings.service.billing_settings_service import BillingSettingsService
from apps.settings.service.billing_validator import BillingSettingsUpdate, BillingSettingsValidator
from apps.settings.service.eu_vat_validation_service import EuVatValidationService
from apps.settings.service.locale_settings_service import LocaleSettingsService, LocaleSettingsUpdate
from apps.settings.service.settings_sections_service import SettingsSectionsService
from apps.settings.service.settings_state_mapper import coerce_settings_state, coerce_two_factor_settings_state


class SettingsFacade:
    def __init__(
        self,
        *,
        core_settings_service,
        sections_lister: Callable[[], tuple] | Callable[[], list] | None = None,
        eu_vat_validation_service: EuVatValidationService | None = None,
        require_eu_vat_validation: bool = True,
    ) -> None:
        self._core_settings_service = core_settings_service
        vat_service = eu_vat_validation_service or EuVatValidationService()
        billing_validator = BillingSettingsValidator(
            eu_vat_validation_service=vat_service,
            require_eu_vat_validation=require_eu_vat_validation,
        )
        self._billing_service = BillingSettingsService(
            core_settings_service=core_settings_service,
            validator=billing_validator,
        )
        self._locale_service = LocaleSettingsService(core_settings_service=core_settings_service)
        self._sections_service = SettingsSectionsService(sections_lister=sections_lister)

    def get_settings(self) -> SettingsState:
        return coerce_settings_state(self._core_settings_service.get_settings_snapshot())

    def get_two_factor_settings(self) -> TwoFactorSettingsState:
        return coerce_two_factor_settings_state(self._core_settings_service.get_two_factor_settings())

    def update_two_factor_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        updated_by: int | None = None,
    ) -> TwoFactorSettingsState:
        state = self._core_settings_service.update_two_factor_settings(
            two_factor_enabled=two_factor_enabled,
            updated_by=updated_by,
        )
        return coerce_two_factor_settings_state(state)

    def get_locale_settings(self) -> LocaleSettingsState:
        return self._locale_service.get_locale_settings()

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> LocaleSettingsState:
        return self._locale_service.update_locale_settings(
            payload=LocaleSettingsUpdate(
                timezone=timezone,
                date_format=date_format,
                time_format=time_format,
            ),
            updated_by=updated_by,
        )

    def get_billing_settings(self) -> BillingSettingsState:
        return self._billing_service.get_billing_settings()

    def update_billing_settings(
        self,
        *,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        updated_by: int | None = None,
    ) -> BillingSettingsState:
        return self._billing_service.update_billing_settings(
            payload=BillingSettingsUpdate(
                billing_customer_type=billing_customer_type,
                billing_full_name=billing_full_name,
                billing_company_name=billing_company_name,
                billing_tax_id=billing_tax_id,
                billing_address_line=billing_address_line,
                billing_postal_code=billing_postal_code,
                billing_city=billing_city,
                billing_region=billing_region,
                billing_country=billing_country,
            ),
            updated_by=updated_by,
        )

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        updated_by: int | None = None,
    ) -> SettingsState:
        billing_payload_data = {
            "billing_customer_type": billing_customer_type,
            "billing_full_name": billing_full_name,
            "billing_company_name": billing_company_name,
            "billing_tax_id": billing_tax_id,
            "billing_address_line": billing_address_line,
            "billing_postal_code": billing_postal_code,
            "billing_city": billing_city,
            "billing_region": billing_region,
            "billing_country": billing_country,
        }
        billing_payload = BillingSettingsUpdate(**billing_payload_data)
        if any(value is not None for value in billing_payload_data.values()):
            billing_payload = self._billing_service.normalize_update(billing_payload)
        payload = {
            "two_factor_enabled": two_factor_enabled,
            "timezone": timezone,
            "date_format": date_format,
            "time_format": time_format,
            "updated_by": updated_by,
        }
        for key, value in billing_payload.__dict__.items():
            if value is not None:
                payload[key] = value
        state = self._core_settings_service.update_settings(**payload)
        return coerce_settings_state(state)

    def get_sections(self) -> list[object]:
        return self._sections_service.get_sections()


__all__ = ["SettingsFacade"]
