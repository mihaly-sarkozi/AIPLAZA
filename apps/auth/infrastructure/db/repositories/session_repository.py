# apps/auth/infrastructure/db/repositories/session_repository.py
# Implementálja: SessionRepositoryInterface (ports/session_repository_interface.py)
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import SessionORM
from apps.auth.ports.session_repository_interface import SessionRepositoryInterface
from apps.auth.domain.session import Session


class SessionRepository(SessionRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def create(self, s: Session) -> Session:
        with self._sf() as db:
            try:
                row = SessionORM(
                    user_id=s.user_id,
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
                    created_at=self._normalize_dt(row.created_at)
                )
            except SQLAlchemyError:
                db.rollback()
                raise

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
                expires_at=self._normalize_dt(row.expires_at),
                created_at=self._normalize_dt(row.created_at),
            )

    def invalidate(self, jti: str) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.jti == jti).update(
                {"valid": False}, synchronize_session=False
            )
            db.commit()

    def invalidate_all_for_user(self, user_id: int) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.user_id == user_id, SessionORM.valid.is_(True)
            ).update({"valid": False}, synchronize_session=False)
            db.commit()

    def invalidate_by_hash(self, token_hash: str) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.token_hash == token_hash, SessionORM.valid.is_(True)
            ).update({"valid": False}, synchronize_session=False)
            db.commit()

    def update(self, s: Session) -> Session:
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.id == s.id).update({
                "valid": s.valid,
                "expires_at": s.expires_at,
                "ip": s.ip,
                "user_agent": s.user_agent,
            }, synchronize_session=False)
            db.commit()
            return s
