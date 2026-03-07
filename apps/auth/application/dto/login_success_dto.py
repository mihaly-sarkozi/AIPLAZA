# apps/auth/application/dto/login_success_dto.py
# Login sikeres visszatérési DTO. Tartalmazza a user adatokat és azokat a tokeneket amikkel tud dolgozni a kliens.
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass

from apps.users.domain.user import User


@dataclass(frozen=True)
class LoginSuccess:
    access_token: str
    refresh_token: str
    user: User
    access_jti: str = ""  # allowlist regisztráláshoz (router); törlés/logout után 401
