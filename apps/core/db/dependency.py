# apps/core/db/dependency.py
# Dependency injection for the database session.
# 2026.03.07 - Sárközi Mihály

from typing import Generator
from sqlalchemy.orm import Session
from infrastructure.persistence.db_session import make_session_factory
from config.settings import settings

SessionLocal = make_session_factory(settings.database_url)

def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
