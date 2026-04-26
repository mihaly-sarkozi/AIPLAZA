from __future__ import annotations

import pytest

from apps.settings.service.settings_facade import SettingsFacade

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _CoreSettingsService:
    def __init__(self) -> None:
        self.update_calls: list[dict[str, object]] = []

    def get_settings_snapshot(self) -> dict[str, object]:
        return {
            "two_factor_enabled": False,
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "time_format": "HH:mm",
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
        self.update_calls.append(
            {
                "two_factor_enabled": two_factor_enabled,
                "timezone": timezone,
                "date_format": date_format,
                "time_format": time_format,
                "updated_by": updated_by,
            }
        )
        return {
            "two_factor_enabled": bool(two_factor_enabled),
            "timezone": timezone or "UTC",
            "date_format": date_format or "YYYY-MM-DD",
            "time_format": time_format or "HH:mm",
        }


class _PartialSnapshotCoreSettingsService(_CoreSettingsService):
    def get_settings_snapshot(self) -> dict[str, object]:
        return {"two_factor_enabled": True}


class _MergingCoreSettingsService(_CoreSettingsService):
    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, object] = {
            "two_factor_enabled": False,
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
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
        self.update_calls.append(
            {
                "two_factor_enabled": two_factor_enabled,
                "timezone": timezone,
                "date_format": date_format,
                "time_format": time_format,
                "updated_by": updated_by,
            }
        )
        if two_factor_enabled is not None:
            self.state["two_factor_enabled"] = two_factor_enabled
        if timezone is not None:
            self.state["timezone"] = timezone
        if date_format is not None:
            self.state["date_format"] = date_format
        if time_format is not None:
            self.state["time_format"] = time_format
        return dict(self.state)


class _Section:
    def __init__(self, *, key: str) -> None:
        self.key = key
        self.label = f"Label {key}"
        self.path = f"/admin/settings?section={key}"
        self.permission = "settings.read"
        self.order = 10
        self.description = "Desc"
        self.source = "core"


def test_get_settings_returns_mapped_core_snapshot() -> None:
    facade = SettingsFacade(core_settings_service=_CoreSettingsService())

    payload = facade.get_settings()

    assert payload == {
        "two_factor_enabled": False,
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
    }


def test_get_settings_coerces_defaults_for_partial_core_snapshot() -> None:
    facade = SettingsFacade(core_settings_service=_PartialSnapshotCoreSettingsService())

    payload = facade.get_settings()

    assert payload == {
        "two_factor_enabled": True,
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
    }


def test_update_settings_delegates_to_core_service() -> None:
    core = _CoreSettingsService()
    facade = SettingsFacade(core_settings_service=core)

    payload = facade.update_settings(
        two_factor_enabled=True,
        timezone="Europe/Budapest",
        date_format="DD.MM.YYYY",
        time_format="HH:mm:ss",
        updated_by=7,
    )

    assert core.update_calls == [
        {
            "two_factor_enabled": True,
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
            "updated_by": 7,
        }
    ]
    assert payload["two_factor_enabled"] is True
    assert payload["timezone"] == "Europe/Budapest"


def test_update_settings_preserves_other_fields_for_partial_update() -> None:
    core = _MergingCoreSettingsService()
    facade = SettingsFacade(core_settings_service=core)

    payload = facade.update_settings(timezone="UTC", updated_by=11)

    assert core.update_calls == [
        {
            "two_factor_enabled": None,
            "timezone": "UTC",
            "date_format": None,
            "time_format": None,
            "updated_by": 11,
        }
    ]
    assert payload == {
        "two_factor_enabled": False,
        "timezone": "UTC",
        "date_format": "DD.MM.YYYY",
        "time_format": "HH:mm:ss",
    }


def test_get_sections_maps_contributor_metadata() -> None:
    facade = SettingsFacade(
        core_settings_service=_CoreSettingsService(),
        sections_lister=lambda: (_Section(key="core.system"), _Section(key="billing")),
    )

    sections = facade.get_sections()

    assert [item["key"] for item in sections] == ["core.system", "billing"]
    assert sections[0]["path"] == "/admin/settings?section=core.system"


def test_get_sections_returns_empty_list_when_sections_lister_missing() -> None:
    facade = SettingsFacade(core_settings_service=_CoreSettingsService(), sections_lister=None)

    assert facade.get_sections() == []
