# backend/core/kernel/runtime/permission_wiring.py
# Feladat: PermissionService példányt hoz létre és feltölti a manifestben összegyűjtött jogosultságokkal. Ezzel a modulok permission deklarációi runtime service-ként elérhetővé válnak a security és admin rétegek számára. Core runtime wiring a platform jogosultság registryhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.app.app_manifest import AppManifest
from core.kernel.security.permission_service import PermissionService


def assemble_permission_service(manifest: AppManifest) -> PermissionService:
    """Új PermissionService, regisztrálva a manifest összes ismert jogosultságával."""
    permission_service = PermissionService()
    permission_service.register_permissions(manifest.permissions)
    return permission_service

