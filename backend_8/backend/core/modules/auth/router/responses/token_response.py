# backend/core/modules/auth/router/responses/token_response.py
# Feladat: Sikeres auth token HTTP válasz Pydantic modellje. Access tokent és user response objektumot tartalmaz, míg a refresh token HttpOnly cookie-ban kerül visszaadásra. Auth HTTP response schema.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel

from core.modules.users.router.responses.user_response import UserResponse


class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse
