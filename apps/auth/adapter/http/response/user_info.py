# apps/auth/adapter/http/response/user_info.py
# Adapter (HTTP): user adatok a token válaszban (TokenResp.user).
# 2026.03.07 - Sárközi Mihály

from pydantic import BaseModel


class UserInfo(BaseModel):
    id: int
    email: str
    role: str  # user | admin | owner
    name: str | None = None
