# backend/core/modules/users/router/requests/user_create_request.py
# Feladat: Admin user létrehozás HTTP request DTO. Email, név, role és kapcsolódó létrehozási adatokat hordoz az admin user CRUD endpointnak. Users admin request contract.
# Sárközi Mihály - 2026.05.21

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from shared.validation import is_valid_email


class UserCreateRequest(BaseModel):
    email: str = Field(..., max_length=100, description="User email cím (ide megy a regisztrációs link)")
    name: str = Field("", max_length=100, description="Felhasználó neve")
    role: Literal["user", "admin", "owner"] = Field(
        default="user",
        description="User szerepkör: 'user' vagy 'admin' (owner csak az első regisztráló)",
    )

    # Ez a metódus ellenőrzi a(z) email logikáját.
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        value = value.strip()
        if not is_valid_email(value):
            raise ValueError("Érvénytelen email cím.")
        return value
