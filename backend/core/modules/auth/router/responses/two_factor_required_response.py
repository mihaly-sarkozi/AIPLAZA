# backend/core/modules/auth/router/responses/two_factor_required_response.py
# Feladat: 2FA folytatást kérő HTTP válasz Pydantic modellje. Pending tokent és challenge típust ad vissza, amelyet a kliens a login második lépéséhez használ. Auth HTTP response schema.
# Sárközi Mihály - 2026.05.21

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
