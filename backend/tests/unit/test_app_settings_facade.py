from __future__ import annotations

import pytest

from apps.settings.service.settings_facade import SettingsFacade
from apps.settings.service.eu_vat_validation_service import EuVatValidationResult, EuVatValidationUnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]

BILLING_DEFAULTS = {
    "billing_company_name": "",
    "billing_tax_id": "",
    "billing_address_line": "",
    "billing_postal_code": "",
    "billing_city": "",
    "billing_region": "",
    "billing_country": "",
    "billing_customer_type": "company",
    "billing_full_name": "",
}


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

    def get_two_factor_settings(self) -> dict[str, object]:
        return {"two_factor_enabled": False}

    def update_two_factor_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.update_calls.append({"two_factor_enabled": two_factor_enabled, "updated_by": updated_by})
        return {"two_factor_enabled": bool(two_factor_enabled)}

    def get_locale_settings(self) -> dict[str, object]:
        return {"timezone": "UTC", "date_format": "YYYY-MM-DD", "time_format": "HH:mm"}

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.update_calls.append(
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

    def get_billing_profile(self) -> dict[str, str]:
        return dict(BILLING_DEFAULTS)

    def update_billing_profile(
        self,
        *,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, str]:
        self.update_calls.append(
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
                "updated_by": updated_by,
            }
        )
        return {
            "billing_customer_type": billing_customer_type or "company",
            "billing_full_name": billing_full_name or "",
            "billing_company_name": billing_company_name or "",
            "billing_tax_id": billing_tax_id or "",
            "billing_address_line": billing_address_line or "",
            "billing_postal_code": billing_postal_code or "",
            "billing_city": billing_city or "",
            "billing_region": billing_region or "",
            "billing_country": billing_country or "",
        }

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.update_calls.append(
            {
                "two_factor_enabled": two_factor_enabled,
                "timezone": timezone,
                "date_format": date_format,
                "time_format": time_format,
                "updated_by": updated_by,
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
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.update_calls.append(
            {
                "two_factor_enabled": two_factor_enabled,
                "timezone": timezone,
                "date_format": date_format,
                "time_format": time_format,
                "updated_by": updated_by,
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
        if two_factor_enabled is not None:
            self.state["two_factor_enabled"] = two_factor_enabled
        if timezone is not None:
            self.state["timezone"] = timezone
        if date_format is not None:
            self.state["date_format"] = date_format
        if time_format is not None:
            self.state["time_format"] = time_format
        for key, value in {
            "billing_customer_type": billing_customer_type,
            "billing_full_name": billing_full_name,
            "billing_company_name": billing_company_name,
            "billing_tax_id": billing_tax_id,
            "billing_address_line": billing_address_line,
            "billing_postal_code": billing_postal_code,
            "billing_city": billing_city,
            "billing_region": billing_region,
            "billing_country": billing_country,
        }.items():
            if value is not None:
                self.state[key] = value
        return dict(self.state)


class _VatValidator:
    def __init__(self, *, valid: bool = True, unavailable: bool = False) -> None:
        self.valid = valid
        self.unavailable = unavailable
        self.calls: list[tuple[str, str]] = []

    def validate(self, *, country_code: str, vat_id: str) -> EuVatValidationResult:
        self.calls.append((country_code, vat_id))
        if self.unavailable:
            raise EuVatValidationUnavailableError("down")
        return EuVatValidationResult(country_code=country_code, vat_number=vat_id, valid=self.valid)


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
        **BILLING_DEFAULTS,
    }


def test_get_settings_coerces_defaults_for_partial_core_snapshot() -> None:
    facade = SettingsFacade(core_settings_service=_PartialSnapshotCoreSettingsService())

    payload = facade.get_settings()

    assert payload == {
        "two_factor_enabled": True,
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
        **BILLING_DEFAULTS,
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
            "billing_customer_type": None,
            "billing_full_name": None,
            "billing_company_name": None,
            "billing_tax_id": None,
            "billing_address_line": None,
            "billing_postal_code": None,
            "billing_city": None,
            "billing_region": None,
            "billing_country": None,
        }
    ]
    assert payload["two_factor_enabled"] is True
    assert payload["timezone"] == "Europe/Budapest"


def test_split_two_factor_settings_delegates_to_core_service() -> None:
    core = _CoreSettingsService()
    facade = SettingsFacade(core_settings_service=core)

    payload = facade.update_two_factor_settings(two_factor_enabled=True, updated_by=7)

    assert core.update_calls == [{"two_factor_enabled": True, "updated_by": 7}]
    assert payload == {"two_factor_enabled": True}


def test_split_locale_settings_delegates_to_core_service() -> None:
    core = _CoreSettingsService()
    facade = SettingsFacade(core_settings_service=core)

    payload = facade.update_locale_settings(
        timezone="Europe/Budapest",
        date_format="DD.MM.YYYY",
        time_format="HH:mm:ss",
        updated_by=7,
    )

    assert core.update_calls == [
        {
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
            "updated_by": 7,
        }
    ]
    assert payload["timezone"] == "Europe/Budapest"


def test_split_billing_settings_validates_and_delegates_to_core_service() -> None:
    core = _CoreSettingsService()
    validator = _VatValidator(valid=True)
    facade = SettingsFacade(core_settings_service=core, eu_vat_validation_service=validator)

    payload = facade.update_billing_settings(
        billing_customer_type="company",
        billing_company_name="Example Kft.",
        billing_tax_id="HU12345678",
        billing_address_line="Fo utca 1.",
        billing_postal_code="1051",
        billing_city="Budapest",
        billing_country="HU",
        updated_by=7,
    )

    assert core.update_calls == [
        {
            "billing_customer_type": "company",
            "billing_full_name": "",
            "billing_company_name": "Example Kft.",
            "billing_tax_id": "HU12345678",
            "billing_address_line": "Fo utca 1.",
            "billing_postal_code": "1051",
            "billing_city": "Budapest",
            "billing_region": None,
            "billing_country": "HU",
            "updated_by": 7,
        }
    ]
    assert payload["billing_company_name"] == "Example Kft."


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
            "billing_customer_type": None,
            "billing_full_name": None,
            "billing_company_name": None,
            "billing_tax_id": None,
            "billing_address_line": None,
            "billing_postal_code": None,
            "billing_city": None,
            "billing_region": None,
            "billing_country": None,
        }
    ]
    assert payload == {
        "two_factor_enabled": False,
        "timezone": "UTC",
        "date_format": "DD.MM.YYYY",
        "time_format": "HH:mm:ss",
        **BILLING_DEFAULTS,
    }


def test_update_settings_accepts_valid_company_billing_payload() -> None:
    core = _MergingCoreSettingsService()
    validator = _VatValidator(valid=True)
    facade = SettingsFacade(core_settings_service=core, eu_vat_validation_service=validator)

    payload = facade.update_settings(
        billing_customer_type="company",
        billing_company_name="Acme Kft.",
        billing_tax_id="hu 12345678",
        billing_country="HU",
        billing_postal_code="1111",
        billing_city="Budapest",
        billing_address_line="Fő utca 1.",
        updated_by=5,
    )

    assert validator.calls == [("HU", "HU12345678")]
    assert payload["billing_customer_type"] == "company"
    assert core.update_calls[-1]["billing_tax_id"] == "HU12345678"


def test_update_settings_accepts_valid_private_billing_payload() -> None:
    core = _MergingCoreSettingsService()
    facade = SettingsFacade(core_settings_service=core)

    payload = facade.update_settings(
        billing_customer_type="private",
        billing_full_name="Teszt Elek",
        billing_country="CH",
        billing_region="Zürich",
        billing_postal_code="8000",
        billing_city="Zürich",
        billing_address_line="Main street 1.",
        updated_by=6,
    )

    assert payload["billing_customer_type"] == "private"
    assert core.update_calls[-1]["billing_company_name"] == ""
    assert core.update_calls[-1]["billing_tax_id"] == ""


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        ({"billing_customer_type": "company", "billing_country": "NO", "billing_company_name": "Nord AS", "billing_tax_id": "NO123", "billing_postal_code": "0010", "billing_city": "Oslo", "billing_address_line": "Street 1."}, 422),
        ({"billing_customer_type": "private", "billing_full_name": "Test User", "billing_company_name": "Should Fail", "billing_country": "HU", "billing_postal_code": "1111", "billing_city": "Budapest", "billing_address_line": "Street 1."}, 422),
        ({"billing_customer_type": "private", "billing_full_name": "Test User", "billing_country": "OTHER", "billing_postal_code": "1111", "billing_city": "Budapest", "billing_address_line": "Street 1."}, 422),
        ({"billing_customer_type": "private", "billing_country": "HU", "billing_postal_code": "1111", "billing_city": "Budapest", "billing_address_line": "Street 1."}, 422),
    ],
)
def test_update_settings_rejects_invalid_billing_payloads(payload: dict[str, str], status_code: int) -> None:
    facade = SettingsFacade(core_settings_service=_MergingCoreSettingsService())

    with pytest.raises(Exception) as exc:
        facade.update_settings(**payload)

    assert getattr(exc.value, "status_code") == status_code


def test_update_settings_rejects_invalid_vies_result() -> None:
    facade = SettingsFacade(
        core_settings_service=_MergingCoreSettingsService(),
        eu_vat_validation_service=_VatValidator(valid=False),
    )

    with pytest.raises(Exception) as exc:
        facade.update_settings(
            billing_customer_type="company",
            billing_company_name="Acme Kft.",
            billing_tax_id="HU12345678",
            billing_country="HU",
            billing_postal_code="1111",
            billing_city="Budapest",
            billing_address_line="Street 1.",
        )

    assert getattr(exc.value, "status_code") == 422


def test_update_settings_maps_vies_unavailable_to_503() -> None:
    facade = SettingsFacade(
        core_settings_service=_MergingCoreSettingsService(),
        eu_vat_validation_service=_VatValidator(unavailable=True),
    )

    with pytest.raises(Exception) as exc:
        facade.update_settings(
            billing_customer_type="company",
            billing_company_name="Acme Kft.",
            billing_tax_id="HU12345678",
            billing_country="HU",
            billing_postal_code="1111",
            billing_city="Budapest",
            billing_address_line="Street 1.",
        )

    assert getattr(exc.value, "status_code") == 503


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
