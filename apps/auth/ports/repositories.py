# apps/auth/ports/repositories.py
"""
User repository interface
"""
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.auth.domain.user import User
    from apps.auth.domain.session import Session


class UserRepositoryPort(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional["User"]:
        ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional["User"]:
        ...
    
    @abstractmethod
    def list_all(self) -> list["User"]:
        """Összes user listázása."""
        ...
    
    @abstractmethod
    def create(self, user: "User") -> "User":
        """Új user létrehozása."""
        ...
    
    @abstractmethod
    def update(self, user: "User") -> "User":
        """User frissítése."""
        ...
    
    @abstractmethod
    def delete(self, user_id: int) -> None:
        """User törlése."""
        ...


class SessionRepositoryPort(ABC):
    @abstractmethod
    def create(self, session: "Session") -> "Session":
        ...

    @abstractmethod
    def get_by_jti(self, jti: str) -> Optional["Session"]:
        ...

    @abstractmethod
    def update(self, session: "Session") -> "Session":
        ...

    @abstractmethod
    def invalidate(self, jti: str) -> None:
        ...

    @abstractmethod
    def invalidate_all_for_user(self, user_id: int) -> None:
        ...

    @abstractmethod
    def invalidate_by_hash(self, token_hash: str) -> None:
        ...
