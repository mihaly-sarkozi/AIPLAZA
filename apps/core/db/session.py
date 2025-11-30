# apps/core/db/session.py
# Connection poolból kivesz egy session-t

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_session_factory(dsn: str):
    engine = create_engine(dsn, future=True)
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
