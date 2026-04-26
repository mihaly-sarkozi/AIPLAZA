# Login sikeres visszatérési DTO. Tartalmazza a user adatokat és azokat a tokeneket amikkel tud dolgozni a kliens.
# 2026.02.28 - Sárközi Mihály

from dataclasses import dataclass

from core.capabilities.users.dto.user import User


@dataclass(frozen=True)
class LoginSuccess:
    access_token: str # Access token
    refresh_token: str # Refresh token
    user: User # User objektum
    access_jti: str = ""  # allowlist regisztráláshoz (router); törlés/logout után 401, ha nincs akkor az empty string lesz
