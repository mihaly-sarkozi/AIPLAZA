# Dependency injection for the database session.
# 2026.03.07 - Sárközi Mihály

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
