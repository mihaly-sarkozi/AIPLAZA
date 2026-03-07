# apps/auth/adapter/http/response/token_resp.py
# Sikeres belépés/refresh: access_token + user. Refresh token KIZÁRÓLAG HttpOnly cookie-ban (NE legyen a body-ban).
# Hardening: a response body soha ne tartalmazzon refresh_token mezőt (XSS nem lophatja).
# 2026.02 - Sárközi Mihály

from apps.auth.adapter.http.response.user_info import UserInfo
from pydantic import BaseModel


class TokenResp(BaseModel):
    """Login/refresh válasz. Csak access_token + user. A refresh token csak Set-Cookie-ban (HttpOnly) kerül kiszolgálásra."""
    access_token: str
    user: UserInfo
    # NINCS refresh_token mező – policy: refresh kizárólag cookie-ban.
