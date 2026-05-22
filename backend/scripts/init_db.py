# Ez a fájl egy futtatható backend segédszkriptet és a hozzá tartozó műveleteket tartalmazza.
import os
import sys
from pathlib import Path

# Backend gyökér a path-on (config, apps importokhoz)
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

from dotenv import load_dotenv


def _resolve_env_path() -> Path:
    candidates = (
        _project_root / ".env",
        _project_root.parent / ".env",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


load_dotenv(_resolve_env_path())

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from apps.registry import load_app_modules
from core.kernel.config.config_loader import settings

from core.kernel.app.app_manifest import AppManifest

from core.modules.tenant.service.tenant_schema_service import (
    register_manifest_tenant_schema_hooks,
    sync_existing_tenant_schemas,
    upgrade_public_schema,
)


def ensure_database_exists(url: str) -> None:
    """Ha az adatbázis nem létezik, létrehozza (PostgreSQL: postgres DB-hez csatlakozva)."""
    parsed = make_url(url)
    db_name = parsed.database
    if not db_name:
        return
    # Csatlakozás a postgres alapértelmezett DB-hez
    parsed = parsed.set(database="postgres")
    server_url = str(parsed)
    engine = create_engine(server_url, future=True, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        r = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name})
        if r.scalar() is None:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Adatbázis létrehozva: {db_name}")
    engine.dispose()


def main() -> None:
    ensure_database_exists(settings.database_url)
    engine = create_engine(settings.database_url, future=True)
    register_manifest_tenant_schema_hooks(
        AppManifest.init_app().add_modules(
            load_app_modules(),
        )
    )
    upgrade_public_schema(engine)
    print("Public migrációk lefuttatva.")
    sync_existing_tenant_schemas(engine)
    print("Minden ismert tenant séma migrációja lefuttatva.")


if __name__ == "__main__":
    main()
