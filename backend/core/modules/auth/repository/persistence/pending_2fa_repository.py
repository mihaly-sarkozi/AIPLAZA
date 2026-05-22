# backend/core/modules/auth/repository/persistence/pending_2fa_repository.py
# Feladat: Pending 2FA login tokenek tenant-séma perzisztencia adaptere. A login első lépése után ideiglenes tokent ment, tokenből user ID-t olvas, majd a második lépéskor consume-olja a tokent. Auth repository réteg a kétlépcsős LoginService flowhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError

from core.modules.auth.models.pending_2fa_orm import Pending2FAORM
from core.kernel.runtime.clock import Clock, SystemClock


class Pending2FARepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory, clock: Clock | None = None):
        self._sf = session_factory
        self._clock = clock or SystemClock()

    # Pending 2FA token létrehozása
    def create(self, token: str, user_id: int, expires_at: datetime, *, created_by: int | None = None) -> None:
        with self._sf() as db:
            try:
                row = Pending2FAORM(
                    token=token,
                    user_id=user_id,
                    expires_at=expires_at,
                    created_by=created_by if created_by is not None else user_id,
                )
                db.add(row)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    # Pending 2FA token lekérése
    def get_user_id(self, token: str) -> int | None:
        now = self._clock.now()
        with self._sf() as db:
            row = db.query(Pending2FAORM).filter(
                Pending2FAORM.token == token,
                Pending2FAORM.expires_at > now,
            ).first()
            return row.user_id if row else None

    # Pending 2FA token használata
    def consume(self, token: str) -> None:
        with self._sf() as db:
            try:
                db.query(Pending2FAORM).filter(Pending2FAORM.token == token).delete(
                    synchronize_session=False
                )
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    # Pending 2FA token lekérése és használata
    def get_user_id_and_consume(self, token: str) -> int | None:
        now = self._clock.now()
        with self._sf() as db:
            try:
                row = db.query(Pending2FAORM).filter(
                    Pending2FAORM.token == token,
                    Pending2FAORM.expires_at > now,
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
