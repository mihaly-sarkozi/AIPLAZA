from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ProfilePreferencesPayload(BaseModel):
    dashboard_layout: Literal["comfortable", "compact"] | None = None
    show_tips: bool | None = None


class ProfilePreferencesResponse(BaseModel):
    app_preferences: ProfilePreferencesPayload


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    app_preferences: ProfilePreferencesPayload | None = None


class ProfileResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    name: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    locale: str
    theme: str
    credentials_password_set: bool = False
    tenant_demo_mode: bool = False
    tenant_kb_has_training: bool = False
    app_preferences: ProfilePreferencesPayload


__all__ = [
    "ProfilePreferencesPayload",
    "ProfilePreferencesResponse",
    "ProfileResponse",
    "ProfileUpdateRequest",
]
