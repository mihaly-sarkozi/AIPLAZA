from __future__ import annotations

import pytest

from apps.settings.domain.settings_state import SettingsState
from apps.settings.mappers.settings_mapper import (
    build_settings_response,
    build_settings_section_response,
)

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]

BILLING_DEFAULTS = {
    "billing_company_name": "",
    "billing_tax_id": "",
    "billing_address_line": "",
    "billing_postal_code": "",
    "billing_city": "",
    "billing_region": "",
    "billing_country": "",
}


def test_build_settings_response_includes_all_fields() -> None:
    payload = build_settings_response(
        SettingsState(
            two_factor_enabled=True,
            timezone="Europe/Budapest",
            date_format="DD.MM.YYYY",
            time_format="HH:mm:ss",
        )
    )

    assert payload == {
        "two_factor_enabled": True,
        "timezone": "Europe/Budapest",
        "date_format": "DD.MM.YYYY",
        "time_format": "HH:mm:ss",
        **BILLING_DEFAULTS,
    }


def test_build_settings_section_response_maps_metadata() -> None:
    section = type(
        "Section",
        (),
        {
            "key": "core.system",
            "label": "Core rendszer",
            "path": "/admin/settings?section=core.system",
            "permission": "settings.read",
            "order": 10,
            "description": "Leiras",
            "source": "core",
        },
    )()

    payload = build_settings_section_response(section)

    assert payload["key"] == "core.system"
    assert payload["path"] == "/admin/settings?section=core.system"
    assert payload["source"] == "core"
