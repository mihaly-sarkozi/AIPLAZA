# apps/auth/infrastructure/db/repositories/two_factor_repository.py
# Implementálja: TwoFactorRepositoryInterface (ports/two_factor_repository_interface.py)
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import TwoFactorCodeORM
from apps.auth.ports.two_factor_repository_interface import TwoFactorRepositoryInterface
from apps.auth.domain.two_factor_code import TwoFactorCode


class TwoFactorRepository(TwoFactorRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def create(self, code: TwoFactorCode) -> TwoFactorCode:
        with self._sf() as db:
            try:
                row = TwoFactorCodeORM(
                    user_id=code.user_id,
                    code=code.code,
                    email=code.email,
                    expires_at=code.expires_at,
                    used=code.used
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return code.persisted(
                    id=row.id,
                    created_at=self._normalize_dt(row.created_at)
                )
            except SQLAlchemyError:
                db.rollback()
                raise

    def get_valid_code(self, user_id: int, code: str) -> TwoFactorCode | None:
        with self._sf() as db:
            row = db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.user_id == user_id,
                TwoFactorCodeORM.code == code,
                TwoFactorCodeORM.used == False,
                TwoFactorCodeORM.expires_at > datetime.now(timezone.utc)
            ).first()
            if not row:
                return None
            return TwoFactorCode(
                id=row.id,
                user_id=row.user_id,
                code=row.code,
                email=row.email,
                expires_at=self._normalize_dt(row.expires_at),
                used=row.used,
                created_at=self._normalize_dt(row.created_at)
            )

    def invalidate_user_codes(self, user_id: int) -> None:
        with self._sf() as db:
            db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.user_id == user_id,
                TwoFactorCodeORM.used == False
            ).update({"used": True}, synchronize_session=False)
            db.commit()

    def mark_as_used(self, code_id: int) -> None:
        with self._sf() as db:
            db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.id == code_id
            ).update({"used": True}, synchronize_session=False)
            db.commit()
