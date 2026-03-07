# apps/auth/adapter/http/response/token_resp.py
# Sikeres belépés után: access_token, refresh_token és user (cookie-ban is beállítjuk a refresh_token-t).
# 2026.02.28 - Sárközi Mihály

from apps.auth.adapter.http.response.user_info import UserInfo
from pydantic import BaseModel


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    user: UserInfo
