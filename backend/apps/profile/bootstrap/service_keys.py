from __future__ import annotations

# backend/apps/profile/bootstrap/service_keys.py
# Feladat: A profile modul runtime service kulcsának definiálása.
# Sárközi Mihály - 2026.05.24

from core.kernel.interface.app_keys import module_service_key

PROFILE_SERVICE = module_service_key("profile")

__all__ = ["PROFILE_SERVICE"]
