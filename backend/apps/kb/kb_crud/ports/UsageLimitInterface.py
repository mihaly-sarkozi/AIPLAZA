from __future__ import annotations

# backend/apps/kb/kb_crud/ports/UsageLimitInterface.py
# Feladat: Tenant-szintű tudástár létrehozási limit szerződése.
# Sárközi Mihály - 2026.06.11

from typing import Any, Protocol


class UsageLimitInterface(Protocol):
    def can_create_kb(self, tenant: Any) -> tuple[bool, str | None]:
        """(engedélyezett, indoklás) — a csomag/limit alapján dönt."""
        ...


__all__ = ["UsageLimitInterface"]
