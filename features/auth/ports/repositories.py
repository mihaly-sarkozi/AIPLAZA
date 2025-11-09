# features/auth/ports/repositories.py
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from features.auth.domain.user import User
    from features.auth.domain.session import Session as DomSession


class UserRepositoryPort(ABC):
    @abstractmethod
    def get_by_email(self, email: str) -> Optional["User"]:
        ...

    @abstractmethod
    def get_by_id(self, user_id: int) -> Optional["User"]:
        ...


class SessionRepositoryPort(ABC):
    @abstractmethod
    def create(self, session: "DomSession") -> "DomSession":
        ...

    @abstractmethod
    def get_by_jti(self, jti: str) -> Optional["DomSession"]:
        ...

    @abstractmethod
    def update(self, session: "DomSession") -> "DomSession":
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
