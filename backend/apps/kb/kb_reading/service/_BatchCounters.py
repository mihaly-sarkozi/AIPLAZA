from __future__ import annotations

# backend/apps/kb/kb_reading/service/_BatchCounters.py
# Feladat: _BatchCounters adatszerkezet.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass
class _BatchCounters:
    """Belső számlálók a kötegelt feldolgozáshoz."""

    accepted_count: int = 0
    failed_count: int = 0
    rejected_count: int = 0
    duplicate_count: int = 0
    total_storage_bytes: int = 0


__all__ = ["_BatchCounters"]
