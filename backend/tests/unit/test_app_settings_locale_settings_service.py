# backend/tests/unit/test_app_settings_locale_settings_service.py
# Feladat: LocaleSettingsService core settings delegálásának unit tesztje.
# Sárközi Mihály - 2026.05.29

from __future__ import annotations

import pytest

from apps.settings.service.locale_settings_service import LocaleSettingsService, LocaleSettingsUpdate

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _CoreSettings:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_locale_settings(self) -> dict[str, str]:
        return {"timezone": "UTC", "date_format": "YYYY-MM-DD", "time_format": "HH:mm"}

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, str]:
        self.calls.append(
            {
                "timezone": timezone,
                "date_format": date_format,
                "time_format": time_format,
                "updated_by": updated_by,
            }
        )
        return {
            "timezone": timezone or "UTC",
            "date_format": date_format or "YYYY-MM-DD",
            "time_format": time_format or "HH:mm",
        }


def test_locale_update_delegates_to_core_settings_service() -> None:
    core = _CoreSettings()
    service = LocaleSettingsService(core_settings_service=core)

    response = service.update_locale_settings(
        payload=LocaleSettingsUpdate(
            timezone="Europe/Budapest",
            date_format="DD.MM.YYYY",
            time_format="HH:mm:ss",
        ),
        updated_by=7,
    )

    assert core.calls == [
        {
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
            "updated_by": 7,
        }
    ]
    assert response.timezone == "Europe/Budapest"
