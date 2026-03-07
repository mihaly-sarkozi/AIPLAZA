# apps/users/adapter/http/request/user_create_req.py
# Adapter (HTTP): user létrehozás POST body. Jelszót a user kapja emailben (regisztrációs link, 24h).
# 2026.03.07 - Sárközi Mihály

from pydantic import BaseModel, Field


class UserCreateReq(BaseModel):
    email: str = Field(..., max_length=100, description="User email cím (ide megy a regisztrációs link)")
    name: str = Field("", max_length=100, description="Felhasználó neve")
    role: str = Field(default="user", description="User szerepkör: 'user' vagy 'admin' (owner csak az első regisztráló)")
