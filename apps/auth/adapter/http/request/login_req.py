# apps/auth/adapter/http/request/login_req.py
# Login paraméterek és ellenőrzések
# 2026.02.28 - Sárközi Mihály

from typing import Optional

from pydantic import BaseModel, Field, model_validator


class LoginReq(BaseModel):
    # login 1. lépés email és password amire egy 2fa tokent kap vissza és egy 2FA kódot küld el a usernek email-en keresztül
    # login 2. lépés a 2fa token és kódot adja meg amit validál és ha rendben akkor egy access és refresh tokenet kap vissza
    email: Optional[str] = Field(None, description="Email (1. lépésben kötelező)")
    password: Optional[str] = Field(None, min_length=1, description="Jelszó (1. lépésben)")
    pending_token: Optional[str] = Field(None, description="1. lépés után kapott token (2. lépésben kötelező)")
    two_factor_code: Optional[str] = Field(None, description="2FA kód (2. lépésben kötelező)")
    auto_login: bool = Field(False, description="Automatikus beléptetés: 30 napos refresh cookie, aktivitásnál kitolódik; különben session cookie. Csak jogosultságváltozás vagy kilépés invalidalja.")

    @model_validator(mode="after")
    def either_step1_or_step2(self):
        step1 = self.email and self.password
        step2 = self.pending_token and self.two_factor_code
        if step1 and step2:
            raise ValueError("Adj meg vagy email+jelszót (1. lépés), vagy pending_token+two_factor_code (2. lépés), ne mindkettőt.")
        if not step1 and not step2:
            raise ValueError("Kell vagy email+jelszó (1. lépés), vagy pending_token+two_factor_code (2. lépés).")
        return self
