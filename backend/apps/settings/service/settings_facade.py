from __future__ import annotations

# backend/apps/settings/service/settings_facade.py
# Feladat: App-szintű settings orchestrator. A core platform settings service adatait SettingsState-re normalizálja és settings sectionöket listáz.
# Sárközi Mihály - 2026.05.24

from collections.abc import Callable

from fastapi import HTTPException

from apps.settings.domain.billing_countries import (
    BILLING_COUNTRY_OTHER,
    is_eu_billing_country,
    is_european_billing_country,
    normalize_billing_country_code,
    normalize_eu_vat_id,
)
from apps.settings.domain.settings_state import SettingsState
from apps.settings.domain.settings_state import BillingSettingsState, LocaleSettingsState, TwoFactorSettingsState
from apps.settings.service.eu_vat_validation_service import (
    EuVatValidationService,
    EuVatValidationUnavailableError,
)


class SettingsFacade:
    DEFAULT_STATE = SettingsState()

    def __init__(
        self,
        *,
        core_settings_service,
        sections_lister: Callable[[], tuple] | Callable[[], list] | None = None,
        eu_vat_validation_service: EuVatValidationService | None = None,
        require_eu_vat_validation: bool = True,
    ) -> None:
        self._core_settings_service = core_settings_service
        self._sections_lister = sections_lister
        self._eu_vat_validation_service = eu_vat_validation_service or EuVatValidationService()
        self._require_eu_vat_validation = require_eu_vat_validation

    @staticmethod
    def _coerce_state(payload: dict[str, object]) -> SettingsState:
        return SettingsState(
            two_factor_enabled=bool(payload.get("two_factor_enabled", False)),
            timezone=str(payload.get("timezone", SettingsFacade.DEFAULT_STATE.timezone) or SettingsFacade.DEFAULT_STATE.timezone),  # type: ignore[arg-type]
            date_format=str(payload.get("date_format", SettingsFacade.DEFAULT_STATE.date_format) or SettingsFacade.DEFAULT_STATE.date_format),  # type: ignore[arg-type]
            time_format=str(payload.get("time_format", SettingsFacade.DEFAULT_STATE.time_format) or SettingsFacade.DEFAULT_STATE.time_format),  # type: ignore[arg-type]
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

    @staticmethod
    def _coerce_two_factor_settings(payload: dict[str, object]) -> TwoFactorSettingsState:
        return TwoFactorSettingsState(two_factor_enabled=bool(payload.get("two_factor_enabled", False)))

    @staticmethod
    def _coerce_locale_settings(payload: dict[str, object]) -> LocaleSettingsState:
        return LocaleSettingsState(
            timezone=str(payload.get("timezone", SettingsFacade.DEFAULT_STATE.timezone) or SettingsFacade.DEFAULT_STATE.timezone),  # type: ignore[arg-type]
            date_format=str(payload.get("date_format", SettingsFacade.DEFAULT_STATE.date_format) or SettingsFacade.DEFAULT_STATE.date_format),  # type: ignore[arg-type]
            time_format=str(payload.get("time_format", SettingsFacade.DEFAULT_STATE.time_format) or SettingsFacade.DEFAULT_STATE.time_format),  # type: ignore[arg-type]
        )

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

    def get_settings(self) -> SettingsState:
        return self._coerce_state(self._core_settings_service.get_settings_snapshot())

    def get_two_factor_settings(self) -> TwoFactorSettingsState:
        return self._coerce_two_factor_settings(self._core_settings_service.get_two_factor_settings())

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
        return self._coerce_two_factor_settings(state)

    def get_locale_settings(self) -> LocaleSettingsState:
        return self._coerce_locale_settings(self._core_settings_service.get_locale_settings())

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> LocaleSettingsState:
        state = self._core_settings_service.update_locale_settings(
            timezone=timezone,
            date_format=date_format,
            time_format=time_format,
            updated_by=updated_by,
        )
        return self._coerce_locale_settings(state)

    def get_billing_settings(self) -> BillingSettingsState:
        return self._coerce_billing_settings(self._core_settings_service.get_billing_profile())

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
        billing_payload = self._validate_billing_payload(
            {
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
        )
        state = self._core_settings_service.update_billing_profile(
            billing_customer_type=billing_payload.get("billing_customer_type"),
            billing_full_name=billing_payload.get("billing_full_name"),
            billing_company_name=billing_payload.get("billing_company_name"),
            billing_tax_id=billing_payload.get("billing_tax_id"),
            billing_address_line=billing_payload.get("billing_address_line"),
            billing_postal_code=billing_payload.get("billing_postal_code"),
            billing_city=billing_payload.get("billing_city"),
            billing_region=billing_payload.get("billing_region"),
            billing_country=billing_payload.get("billing_country"),
            updated_by=updated_by,
        )
        return self._coerce_billing_settings(state)

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
        billing_payload = {
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
        if any(value is not None for value in billing_payload.values()):
            billing_payload = self._validate_billing_payload(billing_payload)
        payload = {
            "two_factor_enabled": two_factor_enabled,
            "timezone": timezone,
            "date_format": date_format,
            "time_format": time_format,
            "updated_by": updated_by,
        }
        for key, value in billing_payload.items():
            if value is not None:
                payload[key] = value
        state = self._core_settings_service.update_settings(**payload)
        return self._coerce_state(state)

    def get_sections(self) -> list[object]:
        if self._sections_lister is None:
            return []
        sections: list[dict[str, object]] = []
        for section in self._sections_lister():
            if isinstance(section, dict):
                sections.append(section)
                continue
            sections.append(
                {
                    "key": getattr(section, "key"),
                    "label": getattr(section, "label"),
                    "path": getattr(section, "path"),
                    "permission": getattr(section, "permission"),
                    "order": getattr(section, "order"),
                    "description": getattr(section, "description", None),
                    "source": getattr(section, "source", None),
                }
            )
        return sections

    def _validate_billing_payload(self, payload: dict[str, str | None]) -> dict[str, str | None]:
        customer_type = (payload.get("billing_customer_type") or "").strip() or "company"
        if customer_type not in {"company", "private"}:
            raise HTTPException(status_code=422, detail="Invalid billing customer type.")
        country = normalize_billing_country_code(payload.get("billing_country"))
        if not country or country == BILLING_COUNTRY_OTHER or not is_european_billing_country(country):
            raise HTTPException(status_code=422, detail="The service currently operates only in Europe.")
        required = {
            "billing_country": country,
            "billing_postal_code": payload.get("billing_postal_code"),
            "billing_city": payload.get("billing_city"),
            "billing_address_line": payload.get("billing_address_line"),
        }
        missing = [key for key, value in required.items() if not str(value or "").strip()]
        if customer_type == "company":
            if not is_eu_billing_country(country):
                raise HTTPException(status_code=422, detail="Company billing is currently available only for EU countries.")
            required_company = {
                "billing_company_name": payload.get("billing_company_name"),
                "billing_tax_id": payload.get("billing_tax_id"),
            }
            missing.extend(key for key, value in required_company.items() if not str(value or "").strip())
            if missing:
                raise HTTPException(status_code=422, detail="All company billing fields are required.")
            normalized_vat = normalize_eu_vat_id(payload.get("billing_tax_id"))
            if self._require_eu_vat_validation:
                try:
                    result = self._eu_vat_validation_service.validate(country_code=country, vat_id=normalized_vat)
                except EuVatValidationUnavailableError as exc:
                    raise HTTPException(status_code=503, detail="EU VAT validation is temporarily unavailable.") from exc
                if not result.valid:
                    raise HTTPException(status_code=422, detail="Invalid EU VAT number.")
            payload["billing_tax_id"] = normalized_vat
            payload["billing_full_name"] = (payload.get("billing_full_name") or "").strip()
        else:
            required_private = {"billing_full_name": payload.get("billing_full_name")}
            missing.extend(key for key, value in required_private.items() if not str(value or "").strip())
            if str(payload.get("billing_company_name") or "").strip() or str(payload.get("billing_tax_id") or "").strip():
                raise HTTPException(status_code=422, detail="Private billing must not include company name or VAT number.")
            if missing:
                raise HTTPException(status_code=422, detail="All private billing fields are required.")
            payload["billing_company_name"] = ""
            payload["billing_tax_id"] = ""
        payload["billing_customer_type"] = customer_type
        payload["billing_country"] = country
        return {key: (value.strip() if isinstance(value, str) else value) for key, value in payload.items()}


__all__ = ["SettingsFacade"]
