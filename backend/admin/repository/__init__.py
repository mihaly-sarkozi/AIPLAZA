# backend/admin/repository/__init__.py
# Feladat: Az admin repository csomag exportfelülete. A PlatformAdminRepository-t teszi elérhetővé, amely az admin felhasználók, sessionök, MFA állapot, security monitoring és IP tiltások perzisztencia műveleteit kezeli. Repository csomagbelépő a service és migrációs kódok számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .platform_admin_repository import PlatformAdminRepository

__all__ = ["PlatformAdminRepository"]
