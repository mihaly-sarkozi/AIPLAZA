# Jelszó módosítás request model.
# 2026.04.03 - Sárközi Mihály

from pydantic import BaseModel, Field, field_validator

from core.platform.auth.password_policy import validate_password_policy


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
