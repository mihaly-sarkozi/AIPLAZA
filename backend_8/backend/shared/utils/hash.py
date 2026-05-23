# backend/shared/utils/hash.py
# Feladat: Egyszerű SHA-256 hex digest helper függvényt tartalmaz. Szöveges tokenek, kódok vagy azonosítók determinisztikus hash-eléséhez ad modulfuggetlen segédet. Shared hash utility.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
