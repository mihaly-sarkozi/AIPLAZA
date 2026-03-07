# apps/users/ports/user_repository_interface.py
# User repository interface
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.users.domain.user import User


class UserRepositoryInterface(ABC):
    """User lekérdezése és mentése (tenant-scoped). Implementáció: users.infrastructure."""
    @abstractmethod
    def get_by_email(self, email: str) -> Optional["User"]:
        """User lekérdezése email alapján."""
        ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional["User"]:  
        """User lekérdezése azonosító alapján."""
        ...

    @abstractmethod
    def get_owner(self) -> Optional["User"]:
        """Tenant owner (egyetlen); alapértelmezett locale/theme forrája."""
        ...

    @abstractmethod
    def exists_owner(self) -> bool:
        """Van-e már owner a tenantben (az első regisztrált lesz owner)."""
        ...

    @abstractmethod
    def list_all(self) -> list["User"]:
        """Minden user listázása."""
        ...

    @abstractmethod
    def create(self, user: "User") -> "User":
        """User létrehozása."""
        ...

    @abstractmethod
    def update(self, user: "User") -> "User":
        """User módosítása."""
        ...

    @abstractmethod
    def delete(self, user_id: int) -> None:
        """User törlése."""
        ...

    @abstractmethod
    def update_password(self, user_id: int, password_hash: str) -> None:
        """Jelszó frissítése."""
        ...

    @abstractmethod
    def record_failed_login(self, user_id: int) -> None:
        """Sikertelen bejelentkezés: növeli a számlálót; ha >= 5, is_active=False (tiltsa ki)."""

    @abstractmethod
    def reset_failed_login(self, user_id: int) -> None:
        """Sikeres bejelentkezés vagy jelszó beállítás: failed_login_attempts = 0."""
