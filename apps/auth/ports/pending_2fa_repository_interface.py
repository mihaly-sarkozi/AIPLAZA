# apps/auth/ports/pending_2fa_repository_interface.py
# INTERFÉSZ – Pending 2FA belépés (1. lépés sikeres, 2. lépésre várunk).
# Token + user_id + expires_at; 2. lépésben token → user_id, majd consume (törlés).
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional


class Pending2FARepositoryInterface(ABC):
    """Interface: 2FA előtti „félbelépés” token tárolása. Implementáció: infrastructure réteg."""
    @abstractmethod
    def create(self, token: str, user_id: int, expires_at: datetime) -> None:
        """Egy pending token létrehozása (1. lépés után)."""
        ...

    @abstractmethod
    def get_user_id(self, token: str) -> Optional[int]:
        """Token alapján user_id visszaadása, ha érvényes és nem járt le (nem törli a pendiget)."""
        ...

    @abstractmethod
    def consume(self, token: str) -> None:
        """Token törlése (sikeres 2FA után)."""
        ...

    @abstractmethod
    def get_user_id_and_consume(self, token: str) -> Optional[int]:
        """Token alapján user_id visszaadása, ha érvényes és nem járt le; utána törli a pendiget."""
        ...
