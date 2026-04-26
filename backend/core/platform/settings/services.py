from __future__ import annotations

from core.capabilities.audit.const.audit_log_action_const import AuditLogAction
from core.capabilities.auth.ports import TwoFactorSettingsReader
from core.platform.settings.ports import SettingsRepositoryPort


class SettingsService(TwoFactorSettingsReader):
    TWO_FACTOR_ENABLED_KEY = "two_factor_enabled"
    TIMEZONE_KEY = "timezone"
    DATE_FORMAT_KEY = "date_format"
    TIME_FORMAT_KEY = "time_format"

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

    def __init__(self, repo: SettingsRepositoryPort, audit_service=None):
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

    def get_settings_snapshot(self) -> dict[str, object]:
        return {
            "two_factor_enabled": self.is_two_factor_enabled(),
            "timezone": self.get_timezone(),
            "date_format": self.get_date_format(),
            "time_format": self.get_time_format(),
        }

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        if two_factor_enabled is not None:
            self.set_two_factor_enabled(two_factor_enabled, updated_by=updated_by)
        if timezone is not None:
            self.set_timezone(timezone, updated_by=updated_by)
        if date_format is not None:
            self.set_date_format(date_format, updated_by=updated_by)
        if time_format is not None:
            self.set_time_format(time_format, updated_by=updated_by)
        return self.get_settings_snapshot()


__all__ = ["SettingsService"]
