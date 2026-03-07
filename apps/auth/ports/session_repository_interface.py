# apps/auth/ports/session_repository_interface.py
# INTERFÉSZ  – A session reprezentálja a bejelentkezési sessiont
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apps.auth.domain.session import Session


class SessionRepositoryInterface(ABC):
    """Interface: Session (refresh token) lekérdezése és mentése. Implementáció: infrastructure réteg."""
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
