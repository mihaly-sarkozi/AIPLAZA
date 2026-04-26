"""PermissionService összeállítás a manifest permissions listája alapján."""
from __future__ import annotations

from core.platform.manifest import PlatformManifest
from core.platform.permissions import PermissionService


def assemble_permission_service(manifest: PlatformManifest) -> PermissionService:
    """Új PermissionService, regisztrálva a manifest összes ismert jogosultságával."""
    permission_service = PermissionService()
    permission_service.register_permissions(manifest.permissions)
    return permission_service
