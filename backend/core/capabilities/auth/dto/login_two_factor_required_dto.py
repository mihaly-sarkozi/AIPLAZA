# Login 2. lépés sikeres visszatérési DTO
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginTwoFactorRequired:
    pending_token: str # Pending token, amit kiküldünk a usernek 2FA kód küldésére
    challenge_type: str = "email"
