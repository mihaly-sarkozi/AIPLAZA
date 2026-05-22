# backend/admin/router/__init__.py
# Feladat: Az admin router csomag exportfelülete. A platform-admin FastAPI routert teszi elérhetővé a modul assembly számára, hogy az AdminCoreModule be tudja kötni a /api/platform-admin útvonalakat. HTTP adapter csomagbelépő.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .admin_router import router

__all__ = ["router"]
