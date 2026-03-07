# apps/auth/infrastructure/db/repositories/two_factor_attempt_repository.py
# 2FA brute-force védelem: próbálkozás számlálók (token / user / IP).
# 2026.03 - Sárközi Mihály

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import TwoFactorAttemptORM
from apps.auth.ports.two_factor_attempt_repository_interface import TwoFactorAttemptRepositoryInterface


class TwoFactorAttemptRepository(TwoFactorAttemptRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _get_or_create(self, db, scope: str, scope_key: str, window_minutes: int):
        row = db.query(TwoFactorAttemptORM).filter(
            TwoFactorAttemptORM.scope == scope,
            TwoFactorAttemptORM.scope_key == scope_key,
        ).first()
        now = self._now()
        if not row:
            row = TwoFactorAttemptORM(
                scope=scope,
                scope_key=scope_key,
                attempts=0,
                window_start_at=now,
            )
            db.add(row)
            db.flush()
        else:
            # Ablak lejárt → nullázás
            if (now - row.window_start_at) > timedelta(minutes=window_minutes):
                row.attempts = 0
                row.window_start_at = now
        return row

    def is_blocked(self, scope: str, scope_key: str, max_attempts: int, window_minutes: int) -> bool:
        with self._sf() as db:
            row = db.query(TwoFactorAttemptORM).filter(
                TwoFactorAttemptORM.scope == scope,
                TwoFactorAttemptORM.scope_key == scope_key,
            ).first()
            if not row:
                return False
            now = self._now()
            if (now - row.window_start_at) > timedelta(minutes=window_minutes):
                return False
            return row.attempts >= max_attempts

    def record_failed(self, scope: str, scope_key: str, window_minutes: int) -> int:
        with self._sf() as db:
            try:
                row = self._get_or_create(db, scope, scope_key, window_minutes)
                row.attempts += 1
                db.commit()
                db.refresh(row)
                return row.attempts
            except SQLAlchemyError:
                db.rollback()
                raise

    def reset_for_success(self, pending_token_key: str, user_id: int, ip: str | None) -> None:
        with self._sf() as db:
            try:
                db.query(TwoFactorAttemptORM).filter(
                    TwoFactorAttemptORM.scope == "token",
                    TwoFactorAttemptORM.scope_key == pending_token_key,
                ).delete(synchronize_session=False)
                db.query(TwoFactorAttemptORM).filter(
                    TwoFactorAttemptORM.scope == "user",
                    TwoFactorAttemptORM.scope_key == str(user_id),
                ).delete(synchronize_session=False)
                if ip:
                    db.query(TwoFactorAttemptORM).filter(
                        TwoFactorAttemptORM.scope == "ip",
                        TwoFactorAttemptORM.scope_key == ip,
                    ).delete(synchronize_session=False)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise
