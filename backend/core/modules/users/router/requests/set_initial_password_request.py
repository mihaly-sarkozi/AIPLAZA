# backend/core/modules/users/router/requests/set_initial_password_request.py
# Feladat: Initial password beállítás HTTP request DTO. Meghívó vagy kezdeti jelszó tokenhez tartozó új jelszót hordozza. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel, Field, field_validator

from shared.validation.password import validate_password_policy


class SetInitialPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=1, description="Új jelszó a konfigurált policy szerint")

    @field_validator("new_password")
    @classmethod
    def new_password_strong(cls, value: str) -> str:
        ok, msg = validate_password_policy(value)
        if not ok:
            raise ValueError(msg or "Invalid password")
        return value
