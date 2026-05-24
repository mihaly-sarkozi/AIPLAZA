from __future__ import annotations

from fastapi import APIRouter, Body

from apps.profile.api.schemas import (
    ProfilePreferencesPayload,
    ProfilePreferencesResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from apps.profile.bootstrap.dependencies import CurrentProfileUserDep, ProfileFacadeDep, ProfileTenantDep

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
    tenant: ProfileTenantDep,
    current_user: CurrentProfileUserDep,
    facade: ProfileFacadeDep,
    body: ProfileUpdateRequest = Body(...),
):
    return facade.update_profile(
        user=current_user,
        tenant=tenant,
        name=body.name,
        preferred_locale=body.preferred_locale,
        preferred_theme=body.preferred_theme,
        app_preferences=body.app_preferences.model_dump(exclude_none=True) if body.app_preferences else None,
    )


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
