# apps/auth/adapter/http/response/two_factor_required_resp.py
# Loginnál a 2. lépéshez szükséges 2fa tokent adja vissza
# 2026.02.28 - Sárközi Mihály

from pydantic import BaseModel, Field

class TwoFactorRequiredResp(BaseModel):
    pending_token: str = Field(
        ...,
        description="2. lépéshez: add vissza a two_factor_code-dal (a kód csak emailben van)"
    )
