# Felhasználó létrehozás request model
# 2026.04.03 - Sárközi Mihály

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
