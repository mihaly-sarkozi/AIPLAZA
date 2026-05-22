# backend/core/modules/auth/router/requests/login_request.py
# Feladat: Az auth login endpoint Pydantic request modellje. Egy modellben validálja, hogy vagy email+jelszó első lépés, vagy pending_token+two_factor_code második lépés érkezzen, de a kettő ne keveredjen. Auth HTTP request schema.
# Sárközi Mihály - 2026.05.21

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LoginRequest(BaseModel):
    email: Optional[str] = Field(None, description="Email (1. lépésben kötelező)")
    password: Optional[str] = Field(None, min_length=1, description="Jelszó (1. lépésben)")
    pending_token: Optional[str] = Field(None, description="1. lépés után kapott token (2. lépésben kötelező)")
    two_factor_code: Optional[str] = Field(None, description="2FA kód (2. lépésben kötelező)")
    auto_login: bool = Field(False, description="Automatikus beléptetés.")

    # Ez a metódus a(z) either_step1_or_step2 logikáját valósítja meg.
    @model_validator(mode="after")
    def either_step1_or_step2(self):
        step1 = self.email and self.password
        step2 = self.pending_token and self.two_factor_code
        if step1 and step2:
            raise ValueError("Adj meg vagy email+jelszót (1. lépés), vagy pending_token+two_factor_code (2. lépés), ne mindkettőt.")
        if not step1 and not step2:
            raise ValueError("Kell vagy email+jelszó (1. lépés), vagy pending_token+two_factor_code (2. lépés).")
        return self
