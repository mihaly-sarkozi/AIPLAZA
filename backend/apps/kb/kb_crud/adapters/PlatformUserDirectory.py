from __future__ import annotations

# backend/apps/kb/kb_crud/adapters/PlatformUserDirectory.py
# Feladat: UserDirectoryInterface adapter — a platform user repository-ra delegál.
# Sárközi Mihály - 2026.06.11

from typing import Any


class PlatformUserDirectory:
    def __init__(self, user_repository: Any) -> None:
        self._user_repository = user_repository

    def list_users(self) -> list[Any]:
        if self._user_repository is None or not hasattr(self._user_repository, "list_all"):
            return []
        return self._user_repository.list_all()


__all__ = ["PlatformUserDirectory"]
