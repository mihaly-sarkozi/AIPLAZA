# backend/core/kernel/interface/app_keys.py
# Feladat: Generikus module.* service kulcsnév helper. Konkrét app kulcsokat nem definiál, mert azok az adott app contracts.py fájljában élnek.
# Sárközi Mihály - 2026.05.21

"""App service key interface.

Generic helper for module-scoped service keys. Concrete app service keys live
in app-local contracts modules, so the core does not know app names.
"""
from __future__ import annotations


def module_service_key(domain: str, suffix: str = "service") -> str:
    domain_slug = (domain or "").strip().lower()
    if not domain_slug:
        raise ValueError("domain must not be empty")
    return f"module.{domain_slug}.{suffix}"


__all__ = ["module_service_key"]
