from __future__ import annotations

# backend/apps/kb/kb_crud/ports/UserDirectoryInterface.py
# Feladat: A tenant felhasználóinak listázása a permission nézetekhez.
# Sárközi Mihály - 2026.06.11

from typing import Any, Protocol


class UserDirectoryInterface(Protocol):
    def list_users(self) -> list[Any]:
        """A tenant összes felhasználója (id, email, name, role attribútumokkal)."""
        ...


__all__ = ["UserDirectoryInterface"]
