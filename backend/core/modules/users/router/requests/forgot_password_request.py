# backend/core/modules/users/router/requests/forgot_password_request.py
# Feladat: Forgot password HTTP request DTO. Email alapú jelszó-visszaállítás indításához szükséges adatokat hordozza. Users web request contract.
# Sárközi Mihály - 2026.05.21

from pydantic import BaseModel, Field


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=100, description="Email cím")
