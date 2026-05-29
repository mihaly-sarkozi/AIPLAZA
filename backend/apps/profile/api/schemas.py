from __future__ import annotations

# backend/apps/profile/api/schemas.py
# Feladat: A profile API request és response Pydantic sémái a /api/profile route-ok számára.
# Sárközi Mihály - 2026.05.24

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

from shared.validation import is_valid_email


class ProfilePreferencesPayload(BaseModel):
    dashboard_layout: Literal["comfortable", "compact"] | None = None
    show_tips: bool | None = None


class ProfilePreferencesResponse(BaseModel):
    app_preferences: ProfilePreferencesPayload


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    preferred_locale: str | None = None
    preferred_theme: str | None = None
    app_preferences: ProfilePreferencesPayload | None = None

    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not is_valid_email(value):
            raise ValueError("Érvénytelen email cím.")
        return value


class ProfileResponse(BaseModel):
    id: int
    email: str
    pending_email: str | None = None
    pending_email_expires_at: datetime | None = None
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
