# Jelszó elfelejtése request model.
# 2026.04.03 - Sárközi Mihály

from pydantic import BaseModel, Field


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=100, description="Email cím")
