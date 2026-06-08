# backend/main.py
# Feladata: a backend composition rootja, amely látható lépésekben építi fel a rendszert.
# Itt találkozik a kötelező core manifest, az addon/app manifest és a FastAPI app factory.
# Sárközi Mihály - 2026.05.17

from __future__ import annotations

import os


def _enable_debugpy_if_requested() -> None:
    """Docker/Cursor attach: DEBUGPY_ENABLE=1 → debugpy a uvicorn folyamatában indul."""
    flag = os.getenv("DEBUGPY_ENABLE", "").strip().lower()
    if flag not in {"1", "true", "yes", "on"}:
        return

    import sys
    from multiprocessing import current_process

    proc_name = current_process().name
    argv = " ".join(sys.argv)
    # uvicorn --reload: a szülő csak figyel, a SpawnProcess-* worker szolgál ki.
    if proc_name == "MainProcess" and "--reload" in argv:
        return
    # Egyszerű (nem reload) indítás vagy reload worker; egyéb script import ne listeneljen.
    if proc_name == "MainProcess" and "uvicorn" not in argv:
        return

    import debugpy

    host = os.getenv("DEBUGPY_HOST", "0.0.0.0")
    port = int(os.getenv("DEBUGPY_PORT", "5678"))
    if debugpy.is_client_connected():
        return

    debugpy.listen((host, port))
    print(f"[debugpy] listening on {host}:{port}", flush=True)

    if os.getenv("DEBUGPY_WAIT_FOR_CLIENT", "").strip().lower() in {"1", "true", "yes", "on"}:
        print("[debugpy] waiting for client attach...", flush=True)
        debugpy.wait_for_client()


_enable_debugpy_if_requested()

from apps.registry import load_app_modules
from core.kernel.app.app_factory import create_app_from_manifest
from core.kernel.app.app_manifest import AppManifest
from core.kernel.config.config_loader import get_settings


# 0. Runtime konfiguráció betöltése.
settings = get_settings()

# 1. Kötelező core rendszer manifest inicializálása.
manifest = AppManifest.init_app()

# 2. Addon/app manifest hozzáadása: ebből lesz a kész runtime manifest.
runtime_manifest = manifest.add_modules(load_app_modules())

# 3. FastAPI alkalmazás létrehozása a kész runtime manifestből.
app = create_app_from_manifest(runtime_manifest, settings=settings)
