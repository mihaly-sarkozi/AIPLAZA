# apps/auth/infrastructure/db/repositories/pending_2fa_repository.py
# Implementálja: Pending2FARepositoryInterface
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import Pending2FAORM
from apps.auth.ports.pending_2fa_repository_interface import Pending2FARepositoryInterface


class Pending2FARepository(Pending2FARepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def create(self, token: str, user_id: int, expires_at: datetime) -> None:
        with self._sf() as db:
            try:
                row = Pending2FAORM(token=token, user_id=user_id, expires_at=expires_at)
                db.add(row)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    def get_user_id_and_consume(self, token: str) -> int | None:
        with self._sf() as db:
            try:
                row = db.query(Pending2FAORM).filter(
                    Pending2FAORM.token == token,
                    Pending2FAORM.expires_at > datetime.now(timezone.utc),
                ).first()
                if not row:
                    return None
                user_id = row.user_id
                db.delete(row)
                db.commit()
                return user_id
            except SQLAlchemyError:
                db.rollback()
                raise
