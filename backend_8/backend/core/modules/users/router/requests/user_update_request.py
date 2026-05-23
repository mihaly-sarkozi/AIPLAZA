# backend/core/modules/users/router/requests/user_update_request.py
# Feladat: Admin user módosítás HTTP request DTO. Role, profil és account mezők részleges frissítését hordozza admin CRUD műveletekhez. Users admin request contract.
# Sárközi Mihály - 2026.05.21

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.validation import is_valid_email


class UserUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=100, description="Felhasználó neve")
    is_active: bool | None = Field(None, description="Aktív státusz")
    email: str | None = Field(None, max_length=100, description="Email")
    role: Literal["user", "admin"] | None = Field(None, description="Szerepkör: user | admin")

    # Ez a metódus ellenőrzi a(z) optional email logikáját.
    @field_validator("email")
    @classmethod
    def validate_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not is_valid_email(value):
            raise ValueError("Érvénytelen email cím.")
        return value
