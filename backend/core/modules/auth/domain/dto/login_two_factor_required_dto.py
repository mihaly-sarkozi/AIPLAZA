# backend/core/modules/auth/domain/dto/login_two_factor_required_dto.py
# Feladat: A login első lépése után visszaadott 2FA challenge DTO-t definiálja. Pending tokent és challenge típust hordoz, hogy a kliens a második lépésben kóddal folytathassa a belépést. Auth domain DTO a LoginService és router között.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass


@dataclass(frozen=True)
class LoginTwoFactorRequired:
    pending_token: str # Pending token, amit kiküldünk a usernek 2FA kód küldésére
    challenge_type: str = "email"
