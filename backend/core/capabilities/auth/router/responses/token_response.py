# Token response model
# 2026.04.03 - Sárközi Mihály

from pydantic import BaseModel

from core.capabilities.users.router.responses.user_response import UserResponse


class TokenResponse(BaseModel):
    access_token: str
    user: UserResponse
