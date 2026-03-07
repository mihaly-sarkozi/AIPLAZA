# apps/auth/application/dto/login_two_factor_required_dto.py
# Login 2. lépés sikeres visszatérési DTO
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginTwoFactorRequired:
    pending_token: str
