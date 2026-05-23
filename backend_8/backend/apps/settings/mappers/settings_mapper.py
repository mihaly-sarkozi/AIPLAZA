from __future__ import annotations

from apps.settings.domain.settings_state import SettingsState


def build_settings_response(state: SettingsState) -> dict[str, object]:
    return {
        "two_factor_enabled": state.two_factor_enabled,
        "timezone": state.timezone,
        "date_format": state.date_format,
        "time_format": state.time_format,
        "billing_company_name": state.billing_company_name,
        "billing_tax_id": state.billing_tax_id,
        "billing_address_line": state.billing_address_line,
        "billing_postal_code": state.billing_postal_code,
        "billing_city": state.billing_city,
        "billing_region": state.billing_region,
        "billing_country": state.billing_country,
    }


def build_settings_section_response(section) -> dict[str, object]:
    return {
        "key": section.key,
        "label": section.label,
        "path": section.path,
        "permission": section.permission,
        "order": section.order,
        "description": section.description,
        "source": section.source,
    }


__all__ = ["build_settings_response", "build_settings_section_response"]
