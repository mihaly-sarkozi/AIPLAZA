from __future__ import annotations

# backend/apps/settings/service/settings_state_mapper.py
# Feladat: Core settings payloadok domain állapot-DTO-kra történő központi leképezése.
# Sárközi Mihály - 2026.05.29

from apps.settings.domain.settings_state import SettingsState, TwoFactorSettingsState

DEFAULT_SETTINGS_STATE = SettingsState()


def coerce_settings_state(payload: dict[str, object]) -> SettingsState:
    return SettingsState(
        two_factor_enabled=bool(payload.get("two_factor_enabled", False)),
        timezone=str(payload.get("timezone", DEFAULT_SETTINGS_STATE.timezone) or DEFAULT_SETTINGS_STATE.timezone),  # type: ignore[arg-type]
        date_format=str(payload.get("date_format", DEFAULT_SETTINGS_STATE.date_format) or DEFAULT_SETTINGS_STATE.date_format),  # type: ignore[arg-type]
        time_format=str(payload.get("time_format", DEFAULT_SETTINGS_STATE.time_format) or DEFAULT_SETTINGS_STATE.time_format),  # type: ignore[arg-type]
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


def coerce_two_factor_settings_state(payload: dict[str, object]) -> TwoFactorSettingsState:
    return TwoFactorSettingsState(two_factor_enabled=bool(payload.get("two_factor_enabled", False)))


__all__ = ["coerce_settings_state", "coerce_two_factor_settings_state"]
