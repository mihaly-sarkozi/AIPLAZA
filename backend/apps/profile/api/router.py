from __future__ import annotations

# backend/apps/profile/api/router.py
# Feladat: A profile HTTP route-ok adaptere a /api/profile és /api/profile/preferences végpontokhoz.
# Sárközi Mihály - 2026.05.24

from fastapi import APIRouter, Body, HTTPException, Request

from apps.profile.api.schemas import (
    ProfilePreferencesPayload,
    ProfilePreferencesResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from apps.profile.bootstrap.dependencies import CurrentProfileUserDep, ProfileFacadeDep, ProfileTenantDep
from core.modules.tenant.helpers import tenant_frontend_base_url_from_request

router = APIRouter()


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    tenant: ProfileTenantDep,
    current_user: CurrentProfileUserDep,
    facade: ProfileFacadeDep,
):
    return facade.get_profile(user=current_user, tenant=tenant)


@router.patch("/profile", response_model=ProfileResponse)
def update_profile(
    request: Request,
    tenant: ProfileTenantDep,
    current_user: CurrentProfileUserDep,
    facade: ProfileFacadeDep,
    body: ProfileUpdateRequest = Body(...),
):
    try:
        return facade.update_profile(
            user=current_user,
            tenant=tenant,
            name=body.name,
            email=body.email,
            preferred_locale=body.preferred_locale,
            preferred_theme=body.preferred_theme,
            app_preferences=body.app_preferences.model_dump(exclude_none=True) if body.app_preferences else None,
            request_base_url=tenant_frontend_base_url_from_request(request),
        )
    except ValueError as exc:
        code = str(exc)
        if code == "email_already_exists":
            raise HTTPException(status_code=400, detail={"code": "email_already_exists", "message": "Ez az email cím már használatban van."})
        if code == "same_email":
            raise HTTPException(status_code=400, detail={"code": "same_email", "message": "Ez már a jelenlegi email címed."})
        raise HTTPException(status_code=400, detail={"code": "validation_error", "message": code})


@router.get("/profile/preferences", response_model=ProfilePreferencesResponse)
def get_profile_preferences(
    tenant: ProfileTenantDep,
    current_user: CurrentProfileUserDep,
    facade: ProfileFacadeDep,
):
    return facade.get_preferences(user=current_user, tenant=tenant)


@router.patch("/profile/preferences", response_model=ProfilePreferencesResponse)
def update_profile_preferences(
    tenant: ProfileTenantDep,
    current_user: CurrentProfileUserDep,
    facade: ProfileFacadeDep,
    body: ProfilePreferencesPayload = Body(...),
):
    return facade.update_preferences(
        user=current_user,
        tenant=tenant,
        app_preferences=body.model_dump(exclude_none=True),
    )


__all__ = ["router"]
