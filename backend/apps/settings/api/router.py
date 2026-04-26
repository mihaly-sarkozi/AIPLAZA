from __future__ import annotations

from fastapi import APIRouter, Body

from apps.settings.api.schemas import SettingsResponse, SettingsSectionResponse, SettingsUpdateRequest
from apps.settings.dependencies import SettingsFacadeDep, SettingsReadUserDep, SettingsWriteUserDep

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    facade: SettingsFacadeDep,
    current_user: SettingsReadUserDep,
):
    return facade.get_settings()


@router.patch("/settings", response_model=SettingsResponse)
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
        updated_by=current_user.id,
    )


@router.get("/settings/sections", response_model=list[SettingsSectionResponse])
def get_settings_sections(
    facade: SettingsFacadeDep,
    current_user: SettingsReadUserDep,
):
    return facade.get_sections()


__all__ = ["router"]
