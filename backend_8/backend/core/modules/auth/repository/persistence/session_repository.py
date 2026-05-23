# backend/core/modules/auth/repository/persistence/session_repository.py
# Feladat: Refresh sessionök tenant-séma perzisztencia adaptere. Session DTO-kat ment, JTI alapján lekér, token hash alapján érvénytelenít, user összes sessionjét visszavonja és frissíti a session állapotot. Auth repository réteg a login, refresh és logout use case-ekhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations
from sqlalchemy.exc import SQLAlchemyError

from shared.utils import normalize_utc_datetime
from core.modules.auth.domain.dto.session import Session
from core.modules.auth.models.session_orm import SessionORM


class SessionRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory):
        self._sf = session_factory

    # Session létrehozása
    def create(self, s: Session, *, created_by: int | None = None) -> Session:
        with self._sf() as db:
            try:
                row = SessionORM(
                    user_id=s.user_id,
                    created_by=created_by if created_by is not None else s.user_id,
                    updated_by=created_by if created_by is not None else s.user_id,
                    jti=s.jti,
                    token_hash=s.token_hash,
                    ip=s.ip,
                    user_agent=s.user_agent,
                    valid=s.valid,
                    expires_at=s.expires_at,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return s.persisted(
                    id=row.id,
                    created_at=normalize_utc_datetime(row.created_at)
                )
            except SQLAlchemyError:
                db.rollback()
                raise

    # Session lekérése
    def get_by_jti(self, jti: str) -> Session | None:
        with self._sf() as db:
            row = db.query(SessionORM).filter(SessionORM.jti == jti).first()
            if not row:
                return None
            return Session(
                id=row.id,
                user_id=row.user_id,
                jti=row.jti,
                token_hash=row.token_hash,
                valid=row.valid,
                ip=row.ip,
                user_agent=row.user_agent,
                expires_at=normalize_utc_datetime(row.expires_at),
                created_at=normalize_utc_datetime(row.created_at),
            )

    # Session visszavonása
    def invalidate(self, jti: str, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.jti == jti).update(
                {"valid": False, "updated_by": updated_by}, synchronize_session=False
            )
            db.commit()

    # Minden session visszavonása userhez
    def invalidate_all_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.user_id == user_id, SessionORM.valid.is_(True)
            ).update({"valid": False, "updated_by": updated_by if updated_by is not None else user_id}, synchronize_session=False)
            db.commit()

    # Session visszavonása token hash alapján
    def invalidate_by_hash(self, token_hash: str, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.token_hash == token_hash, SessionORM.valid.is_(True)
            ).update({"valid": False, "updated_by": updated_by}, synchronize_session=False)
            db.commit()

    # Session frissítése
    def update(self, s: Session, *, updated_by: int | None = None) -> Session:
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.id == s.id).update({
                "valid": s.valid,
                "expires_at": s.expires_at,
                "ip": s.ip,
                "user_agent": s.user_agent,
                "updated_by": updated_by if updated_by is not None else s.user_id,
            }, synchronize_session=False)
            db.commit()
            return s
