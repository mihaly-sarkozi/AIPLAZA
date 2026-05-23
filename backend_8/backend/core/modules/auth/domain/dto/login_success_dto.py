# backend/core/modules/auth/domain/dto/login_success_dto.py
# Feladat: Sikeres login use case eredmény DTO-t definiál. Tartalmazza az access tokent, refresh tokent, user objektumot és az access token JTI-t, amelyet a router allowlistbe regisztrál. Auth domain DTO a LoginService és HTTP response builder között.
# Sárközi Mihály - 2026.05.21

from dataclasses import dataclass

from core.modules.users.domain.dto.user import User


@dataclass(frozen=True)
class LoginSuccess:
    access_token: str # Access token
    refresh_token: str # Refresh token
    user: User # User objektum
    access_jti: str = ""  # allowlist regisztráláshoz (router); törlés/logout után 401, ha nincs akkor az empty string lesz
