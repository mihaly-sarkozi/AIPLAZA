# backend/core/kernel/db/dependency.py
# Feladat: FastAPI dependencyként használható DB session providert ad. A központi settings alapján létrehozott SessionLocal factoryt használja, és request scope-ban yieldeli a sessiont. Általános core HTTP/DB adapter, bár az újabb runtime útvonalak inkább az InfrastructureRegistry session factoryját használják.
# Sárközi Mihály - 2026.05.21

from typing import Generator

from core.kernel.config.config_loader import settings
from core.kernel.db.session import make_session_factory

SessionLocal = make_session_factory(
    settings.database_url,
    pool_pre_ping=getattr(settings, "database_pool_pre_ping", True),
)

# Ez a függvény visszaadja a(z) session logikáját.
def get_session() -> Generator[object, None, None]:
    with SessionLocal() as db:
        yield db
