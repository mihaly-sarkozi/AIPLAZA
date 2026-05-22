# backend/main.py
# Feladata: a backend composition rootja, amely látható lépésekben építi fel a rendszert.
# Itt találkozik a kötelező core manifest, az addon/app manifest és a FastAPI app factory.
# Sárközi Mihály - 2026.05.17

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
