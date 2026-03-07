# apps/users/adapter/http/request/set_password_req.py
# Adapter (HTTP): jelszó beállítás a meghívott usernek (token + jelszó).
# 2026.03.07 - Sárközi Mihály

import re
from pydantic import BaseModel, Field, field_validator


def validate_password_strength(value: str) -> tuple[bool, str | None]:
    """
    Egységes jelszószabály: min 6 karakter, legalább egy kisbetű, egy nagybetű, egy szám.
    Returns (ok, error_message).
    """
    if len(value) < 6:
        return False, "A jelszónak legalább 6 karakter hosszúnak kell lennie."
    if not re.search(r"[a-z]", value):
        return False, "A jelszónak tartalmaznia kell legalább egy kisbetűt."
    if not re.search(r"[A-Z]", value):
        return False, "A jelszónak tartalmaznia kell legalább egy nagybetűt."
    if not re.search(r"\d", value):
        return False, "A jelszónak tartalmaznia kell legalább egy számot."
    return True, None


class SetPasswordReq(BaseModel):
    token: str = Field(..., min_length=1, description="Emailben kapott jelszó beállító token")
    password: str = Field(..., min_length=6, description="Új jelszó (min. 6 karakter, kisbetű, nagybetű, szám)")

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        ok, msg = validate_password_strength(v)
        if not ok:
            raise ValueError(msg)
        return v
