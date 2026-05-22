# backend/core/kernel/app/app_bootstrap.py
# Feladat: A manifesthez tartozó indulás előtti runtime hookokat futtatja. Itt történik a modulok bootstrap hookjainak meghívása és a tenant schema hookok központi regisztrálása, mielőtt a FastAPI app kiszolgálni kezdene. Az app factory hívja, ezért ez a fájl a manifest és a runtime előkészítés közötti általános kernel-kapcsolat.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.kernel.app.app_manifest import AppManifest
from core.modules.tenant.service import register_manifest_tenant_schema_hooks


def bootstrap_manifest_runtime(manifest: AppManifest) -> None:
    """Manifest bootstrap hookok futtatása és tenant schema hookok regisztrálása."""
    for hook in manifest.bootstrap_hooks:
        hook()
    register_manifest_tenant_schema_hooks(manifest)


__all__ = ["bootstrap_manifest_runtime"]
