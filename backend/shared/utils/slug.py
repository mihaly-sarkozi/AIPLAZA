from __future__ import annotations

import re


def normalize_slug(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9\s\-]", "", (name or "").strip())
    safe = re.sub(r"\s+", "-", safe).strip("-").lower()[:64]
    return safe


def slug_is_valid(slug: str) -> bool:
    return bool(slug and re.match(r"^[a-z0-9][a-z0-9_-]*$", slug) and len(slug) <= 64)
