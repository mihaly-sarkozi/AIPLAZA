from __future__ import annotations

# backend/apps/kb/kb_reading/domain/DuplicatePolicy.py
# Feladat: Ismétlődő tartalom kezelésének szabályai.
# Sárközi Mihály - 2026.06.07

from dataclasses import dataclass


@dataclass(frozen=True)
class DuplicatePolicy:
    """Ismétlődő tartalom kezelésének beállításai."""

    reject_file_duplicate: bool = True
    url_same_origin_refetch: bool = True


DEFAULT_DUPLICATE_POLICY = DuplicatePolicy()

__all__ = ["DEFAULT_DUPLICATE_POLICY", "DuplicatePolicy"]
