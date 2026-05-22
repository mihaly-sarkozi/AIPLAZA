# backend/admin/service/__init__.py
# Feladat: Az admin service csomag exportfelülete. A PlatformAdminService-t adja tovább, amely a platform-admin autentikációs, MFA, user management és monitoring üzleti műveleteit fogja össze. Service csomagbelépő a modul assembly és router számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from .platform_admin_service import PlatformAdminService

__all__ = ["PlatformAdminService"]
