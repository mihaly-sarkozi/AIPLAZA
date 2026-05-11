# 2FA kód szükséges response model
# 2026.04.03 - Sárközi Mihály

from pydantic import BaseModel, Field


class TwoFactorRequiredResponse(BaseModel):
    pending_token: str = Field(
        ...,
        description="2. lépéshez add vissza a two_factor_code-dal.",
    )
    challenge_type: str = Field(
        default="email",
        description="A 2FA challenge típusa: email vagy authenticator.",
    )
