# backend/core/modules/users/router/requests/set_password_request.py
# Feladat: Set password HTTP request DTO. Invite token és új jelszó adatokat hordoz a meghívó elfogadási folyamathoz. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel, Field, field_validator
from shared.validation.password import validate_password_policy


class SetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Emailben kapott jelszó beállító token")
    password: str = Field(..., min_length=1, description="Új jelszó a konfigurált biztonsági policy szerint")

    # Ez a metódus a(z) token_not_blank logikáját valósítja meg.
    @field_validator("token")
    @classmethod
    def token_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A token kötelező.")
        return value

    # Ez a metódus a(z) password_strong logikáját valósítja meg.
    @field_validator("password")
    @classmethod
    def password_strong(cls, value: str) -> str:
        ok, message = validate_password_policy(value)
        if not ok:
            raise ValueError(message)
        return value
