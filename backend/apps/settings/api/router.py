from __future__ import annotations

# backend/apps/settings/api/router.py
# Feladat: A settings modul FastAPI routere. Beállítások olvasását, módosítását és settings szekciók listázását delegálja a SettingsFacade felé.
# Sárközi Mihály - 2026.05.24

from fastapi import APIRouter, Body

from apps.settings.api.SettingsSectionResponse import SettingsSectionResponse
from apps.settings.api.SettingsUpdateRequest import SettingsUpdateRequest
from apps.settings.bootstrap.dependencies import SettingsFacadeDep, SettingsReadUserDep, SettingsWriteUserDep
from apps.settings.domain.settings_state import SettingsState

router = APIRouter()


@router.get("/settings", response_model=SettingsState)
def get_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsReadUserDep,
):
    return facade.get_settings()


@router.patch("/settings", response_model=SettingsState)
def update_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsWriteUserDep,
    body: SettingsUpdateRequest = Body(default=SettingsUpdateRequest()),
):
    return facade.update_settings(
        two_factor_enabled=body.two_factor_enabled,
        timezone=body.timezone,
        date_format=body.date_format,
        time_format=body.time_format,
        billing_company_name=body.billing_company_name,
        billing_tax_id=body.billing_tax_id,
        billing_address_line=body.billing_address_line,
        billing_postal_code=body.billing_postal_code,
        billing_city=body.billing_city,
        billing_region=body.billing_region,
        billing_country=body.billing_country,
        updated_by=current_user.id,
    )


@router.get("/settings/sections", response_model=list[SettingsSectionResponse])
def get_settings_sections(
    facade: SettingsFacadeDep,
    current_user: SettingsReadUserDep,
):
    return facade.get_sections()


__all__ = ["router"]
