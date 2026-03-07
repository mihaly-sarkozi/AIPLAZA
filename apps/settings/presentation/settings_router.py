# apps/settings/presentation/settings_router.py
# Beállítások kezelése (csak owner / superuser).
# 2026.03.07 - Sárközi Mihály

from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel

from apps.core.di import get_settings_service, set_tenant_context_from_request
from apps.core.security.auth_dependencies import get_current_user
from apps.users.domain.user import User
from apps.settings.application.services.settings_service import SettingsService
from apps.settings.adapter.http.response import SettingsResp

router = APIRouter(dependencies=[Depends(set_tenant_context_from_request)])


def get_current_owner(user: User = Depends(get_current_user)) -> User:
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can access settings")
    return user


class SettingsUpdateBody(BaseModel):
    two_factor_enabled: bool


@router.get("/settings", response_model=SettingsResp)
def get_settings(
    svc: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(get_current_owner),
):
    return SettingsResp(two_factor_enabled=svc.is_two_factor_enabled())


@router.patch("/settings", response_model=SettingsResp)
def update_settings(
    body: SettingsUpdateBody = Body(...),
    svc: SettingsService = Depends(get_settings_service),
    current_user: User = Depends(get_current_owner),
):
    svc.set_two_factor_enabled(body.two_factor_enabled, updated_by=current_user.id)
    return SettingsResp(two_factor_enabled=svc.is_two_factor_enabled())
