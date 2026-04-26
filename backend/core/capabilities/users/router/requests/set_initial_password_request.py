# Demo: első saját jelszó beállítása (régi jelszó nélkül).
# 2026.04.11 - Sárközi Mihály

from pydantic import BaseModel, Field, field_validator

from core.platform.auth.password_policy import validate_password_policy


class SetInitialPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=1, description="Új jelszó a konfigurált policy szerint")

    @field_validator("new_password")
    @classmethod
    def new_password_strong(cls, value: str) -> str:
        ok, msg = validate_password_policy(value)
        if not ok:
            raise ValueError(msg or "Invalid password")
        return value
