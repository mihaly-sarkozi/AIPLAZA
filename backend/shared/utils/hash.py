# backend/shared/utils/hash.py
# Feladat: SHA-256 hex digest helper függvények szöveghez és bájtokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_text(content: str) -> str:
    """Lenyomat szöveges tartalomból (UTF-8)."""
    return sha256_hex(content)


def sha256_bytes(content: bytes) -> str:
    """Lenyomat bájttömbből."""
    return hashlib.sha256(content).hexdigest()


__all__ = ["sha256_bytes", "sha256_hex", "sha256_text"]
