# backend/core/modules/users/router/requests/change_password_request.py
# Feladat: Jelszócsere HTTP request DTO. A régi és új jelszó adatokat validálható Pydantic modellben hordozza a profile router számára. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel, Field, field_validator

from shared.validation.password import validate_password_policy


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Jelenlegi jelszó")
    new_password: str = Field(..., min_length=1, description="Új jelszó a konfigurált biztonsági policy szerint")

    # Ez a metódus a(z) new_password_strong logikáját valósítja meg.
    @field_validator("new_password")
    @classmethod
    def new_password_strong(cls, value: str) -> str:
        ok, msg = validate_password_policy(value)
        if not ok:
            raise ValueError(msg or "Invalid password")
        return value
