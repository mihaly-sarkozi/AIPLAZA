# apps/users/ports/invite_token_repository_interface.py
# Jelszó beállító link tokenek repository interface
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class InviteTokenRecord:
    id: int
    user_id: int
    expires_at: datetime
    used_at: Optional[datetime]


class InviteTokenRepositoryInterface(ABC):
    @abstractmethod
    def create(self, user_id: int, token_hash: str, expires_at: datetime) -> int:
        """Meghívó token létrehozása."""
        ...

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> Optional[InviteTokenRecord]:
        """Meghívó token lekérdezése a hash alapján."""
        ...

    @abstractmethod
    def mark_used(self, token_id: int) -> None:
        """Meghívó token használatának jelzése."""
        ...

    @abstractmethod
    def invalidate_all_for_user(self, user_id: int) -> None:
        """A user összes meghívó tokenjét érvényteleníteti (mindig csak egy élő link legyen)."""
        ...

    @abstractmethod
    def get_user_ids_with_used_token(self) -> set[int]:
        """Azon user_id-k, akiknek van már használt (regisztrációt teljesítő) meghívó tokenje."""
        ...
