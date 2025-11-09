# apps/api/schemas/auth.py
from pydantic import BaseModel


class LoginReq(BaseModel):
    email: str
    password: str


class TokenResp(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 15 * 60
