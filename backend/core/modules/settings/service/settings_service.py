# backend/core/modules/settings/service/settings_service.py
# Feladat: A perzisztált tenant beállítások application service-e. Kétfaktoros hitelesítés, időzóna, dátum/idő formátum és billing profil beállításokat olvas/frissít validált értékekkel, valamint audit eseményt ír a security settings változásokról. Settings service réteg, amelyet auth és app settings API is használ.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from typing import TYPE_CHECKING

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.auth.domain.ports import TwoFactorSettingsReader

if TYPE_CHECKING:
    from core.modules.settings.repository.settings_repository import SettingsRepository


class SettingsService(TwoFactorSettingsReader):
    TWO_FACTOR_ENABLED_KEY = "two_factor_enabled"
    TIMEZONE_KEY = "timezone"
    DATE_FORMAT_KEY = "date_format"
    TIME_FORMAT_KEY = "time_format"
    BILLING_CUSTOMER_TYPE_KEY = "billing_customer_type"
    BILLING_FULL_NAME_KEY = "billing_full_name"
    BILLING_COMPANY_NAME_KEY = "billing_company_name"
    BILLING_TAX_ID_KEY = "billing_tax_id"
    BILLING_ADDRESS_LINE_KEY = "billing_address_line"
    BILLING_POSTAL_CODE_KEY = "billing_postal_code"
    BILLING_CITY_KEY = "billing_city"
    BILLING_REGION_KEY = "billing_region"
    BILLING_COUNTRY_KEY = "billing_country"

    DEFAULT_TIMEZONE = "UTC"
    DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
    DEFAULT_TIME_FORMAT = "HH:mm"

    ALLOWED_TIMEZONES = {
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
    }
    ALLOWED_DATE_FORMATS = {
        "YYYY-MM-DD",
        "DD.MM.YYYY",
        "DD/MM/YYYY",
        "MM/DD/YYYY",
    }
    ALLOWED_TIME_FORMATS = {
        "HH:mm",
        "HH:mm:ss",
        "hh:mm A",
    }

    def __init__(self, repo: SettingsRepository, audit_service=None):
        self._repo = repo
        self._audit = audit_service

    def is_two_factor_enabled(self) -> bool:
        value = self._repo.get_by_key(self.TWO_FACTOR_ENABLED_KEY)
        if value is None:
            return False
        return value.lower() == "true"

    def set_two_factor_enabled(self, enabled: bool, updated_by: int | None = None) -> None:
        previous_value = self.is_two_factor_enabled()
        value = "true" if enabled else "false"
        self._repo.set_value(
            self.TWO_FACTOR_ENABLED_KEY,
            value,
            updated_by=updated_by,
        )
        if self._audit and previous_value != enabled:
            self._audit.log(
                AuditLogAction.SETTINGS_SECURITY_UPDATED,
                user_id=updated_by,
                details={
                    "setting_key": self.TWO_FACTOR_ENABLED_KEY,
                    "old_value": previous_value,
                    "new_value": enabled,
                },
                target_id=self.TWO_FACTOR_ENABLED_KEY,
            )

    def get_two_factor_settings(self) -> dict[str, bool]:
        return {"two_factor_enabled": self.is_two_factor_enabled()}

    def update_two_factor_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        updated_by: int | None = None,
    ) -> dict[str, bool]:
        if two_factor_enabled is not None:
            self.set_two_factor_enabled(two_factor_enabled, updated_by=updated_by)
        return self.get_two_factor_settings()

    def get_timezone(self) -> str:
        value = self._repo.get_by_key(self.TIMEZONE_KEY)
        if value in self.ALLOWED_TIMEZONES:
            return value
        return self.DEFAULT_TIMEZONE

    def set_timezone(self, timezone: str, updated_by: int | None = None) -> None:
        normalized = str(timezone or "").strip()
        if normalized not in self.ALLOWED_TIMEZONES:
            raise ValueError("invalid_timezone")
        self._repo.set_value(
            self.TIMEZONE_KEY,
            normalized,
            updated_by=updated_by,
        )

    def get_date_format(self) -> str:
        value = self._repo.get_by_key(self.DATE_FORMAT_KEY)
        if value in self.ALLOWED_DATE_FORMATS:
            return value
        return self.DEFAULT_DATE_FORMAT

    def set_date_format(self, date_format: str, updated_by: int | None = None) -> None:
        normalized = str(date_format or "").strip()
        if normalized not in self.ALLOWED_DATE_FORMATS:
            raise ValueError("invalid_date_format")
        self._repo.set_value(
            self.DATE_FORMAT_KEY,
            normalized,
            updated_by=updated_by,
        )

    def get_time_format(self) -> str:
        value = self._repo.get_by_key(self.TIME_FORMAT_KEY)
        if value in self.ALLOWED_TIME_FORMATS:
            return value
        return self.DEFAULT_TIME_FORMAT

    def set_time_format(self, time_format: str, updated_by: int | None = None) -> None:
        normalized = str(time_format or "").strip()
        if normalized not in self.ALLOWED_TIME_FORMATS:
            raise ValueError("invalid_time_format")
        self._repo.set_value(
            self.TIME_FORMAT_KEY,
            normalized,
            updated_by=updated_by,
        )

    def get_locale_settings(self) -> dict[str, str]:
        return {
            "timezone": self.get_timezone(),
            "date_format": self.get_date_format(),
            "time_format": self.get_time_format(),
        }

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, str]:
        before = self.get_settings_snapshot()
        if timezone is not None:
            self.set_timezone(timezone, updated_by=updated_by)
        if date_format is not None:
            self.set_date_format(date_format, updated_by=updated_by)
        if time_format is not None:
            self.set_time_format(time_format, updated_by=updated_by)
        after = self.get_settings_snapshot()
        self._audit_settings_changed(before=before, after=after, updated_by=updated_by)
        return self.get_locale_settings()

    def _get_text_setting(self, key: str) -> str:
        return str(self._repo.get_by_key(key) or "")

    def _set_text_setting(self, key: str, value: str | None, *, updated_by: int | None = None) -> None:
        if value is None:
            return
        self._repo.set_value(key, str(value).strip()[:500], updated_by=updated_by)

    def get_billing_profile(self) -> dict[str, str]:
        return {
            "billing_customer_type": self._get_text_setting(self.BILLING_CUSTOMER_TYPE_KEY) or "company",
            "billing_full_name": self._get_text_setting(self.BILLING_FULL_NAME_KEY),
            "billing_company_name": self._get_text_setting(self.BILLING_COMPANY_NAME_KEY),
            "billing_tax_id": self._get_text_setting(self.BILLING_TAX_ID_KEY),
            "billing_address_line": self._get_text_setting(self.BILLING_ADDRESS_LINE_KEY),
            "billing_postal_code": self._get_text_setting(self.BILLING_POSTAL_CODE_KEY),
            "billing_city": self._get_text_setting(self.BILLING_CITY_KEY),
            "billing_region": self._get_text_setting(self.BILLING_REGION_KEY),
            "billing_country": self._get_text_setting(self.BILLING_COUNTRY_KEY),
        }

    def update_billing_profile(
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
    ) -> dict[str, str]:
        before = self.get_settings_snapshot()
        self._set_text_setting(self.BILLING_CUSTOMER_TYPE_KEY, billing_customer_type, updated_by=updated_by)
        self._set_text_setting(self.BILLING_FULL_NAME_KEY, billing_full_name, updated_by=updated_by)
        self._set_text_setting(self.BILLING_COMPANY_NAME_KEY, billing_company_name, updated_by=updated_by)
        self._set_text_setting(self.BILLING_TAX_ID_KEY, billing_tax_id, updated_by=updated_by)
        self._set_text_setting(self.BILLING_ADDRESS_LINE_KEY, billing_address_line, updated_by=updated_by)
        self._set_text_setting(self.BILLING_POSTAL_CODE_KEY, billing_postal_code, updated_by=updated_by)
        self._set_text_setting(self.BILLING_CITY_KEY, billing_city, updated_by=updated_by)
        self._set_text_setting(self.BILLING_REGION_KEY, billing_region, updated_by=updated_by)
        self._set_text_setting(self.BILLING_COUNTRY_KEY, billing_country, updated_by=updated_by)
        after = self.get_settings_snapshot()
        self._audit_settings_changed(before=before, after=after, updated_by=updated_by)
        return self.get_billing_profile()

    def get_settings_snapshot(self) -> dict[str, object]:
        return {
            **self.get_two_factor_settings(),
            **self.get_locale_settings(),
            **self.get_billing_profile(),
        }

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
    ) -> dict[str, object]:
        if two_factor_enabled is not None:
            self.update_two_factor_settings(two_factor_enabled=two_factor_enabled, updated_by=updated_by)
        if timezone is not None or date_format is not None or time_format is not None:
            self.update_locale_settings(
                timezone=timezone,
                date_format=date_format,
                time_format=time_format,
                updated_by=updated_by,
            )
        if any(
            value is not None
            for value in (
                billing_customer_type,
                billing_full_name,
                billing_company_name,
                billing_tax_id,
                billing_address_line,
                billing_postal_code,
                billing_city,
                billing_region,
                billing_country,
            )
        ):
            self.update_billing_profile(
                billing_customer_type=billing_customer_type,
                billing_full_name=billing_full_name,
                billing_company_name=billing_company_name,
                billing_tax_id=billing_tax_id,
                billing_address_line=billing_address_line,
                billing_postal_code=billing_postal_code,
                billing_city=billing_city,
                billing_region=billing_region,
                billing_country=billing_country,
                updated_by=updated_by,
            )
        return self.get_settings_snapshot()

    def _audit_settings_changed(
        self,
        *,
        before: dict[str, object],
        after: dict[str, object],
        updated_by: int | None,
    ) -> None:
        if not self._audit:
            return
        changed_keys = [
            key
            for key, value in after.items()
            if key != self.TWO_FACTOR_ENABLED_KEY and before.get(key) != value
        ]
        if not changed_keys:
            return
        self._audit.log(
            AuditLogAction.SETTINGS_SECURITY_UPDATED,
            user_id=updated_by,
            target_type="tenant_settings",
            details={
                "changed_keys": changed_keys,
                "changed_count": len(changed_keys),
            },
        )


__all__ = ["SettingsService"]
