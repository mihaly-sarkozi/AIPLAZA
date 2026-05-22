# backend/core/modules/auth/repository/persistence/two_factor_attempt_repository.py
# Feladat: 2FA brute-force próbálkozásszámlálók tenant-séma perzisztencia adaptere. Token, user és IP scope alapján ellenőrzi a limitet, sikertelen próbálkozást rögzít, siker után pedig törli a számlálókat. Auth repository réteg a TwoFactorService limit enforcementhez.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations
from datetime import timedelta
from sqlalchemy.exc import SQLAlchemyError

from shared.utils import normalize_utc_datetime

from core.modules.auth.models.two_factor_attempt_orm import TwoFactorAttemptORM
from core.kernel.runtime.clock import Clock, SystemClock


class TwoFactorAttemptRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory, clock: Clock | None = None):
        self._sf = session_factory
        self._clock = clock or SystemClock()

    # Ez a metódus a(z) now logikáját valósítja meg.
    def _now(self):
        return self._clock.now()

    # Próbálkozás számláló létrehozása vagy frissítése
    def _get_or_create(self, db, scope: str, scope_key: str, window_minutes: int, actor_user_id: int):
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
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            db.add(row)
            db.flush()
        else:
            # Ablak lejárt → nullázás (DB-ből naive UTC is jöhet; now aware)
            wstart = normalize_utc_datetime(row.window_start_at)
            if (now - wstart) > timedelta(minutes=window_minutes):
                row.attempts = 0
                row.window_start_at = now
                row.updated_by = actor_user_id
        return row

    # Próbálkozás számláló lekérése
    def is_blocked(self, scope: str, scope_key: str, max_attempts: int, window_minutes: int) -> bool:
        with self._sf() as db:
            row = db.query(TwoFactorAttemptORM).filter(
                TwoFactorAttemptORM.scope == scope,
                TwoFactorAttemptORM.scope_key == scope_key,
            ).first()
            if not row:
                return False
            now = self._now()
            wstart = normalize_utc_datetime(row.window_start_at)
            if (now - wstart) > timedelta(minutes=window_minutes):
                return False
            return row.attempts >= max_attempts

    # Próbálkozás számláló frissítése
    def record_failed(self, scope: str, scope_key: str, window_minutes: int, *, actor_user_id: int) -> int:
        with self._sf() as db:
            try:
                row = self._get_or_create(db, scope, scope_key, window_minutes, actor_user_id)
                row.attempts += 1
                row.updated_by = actor_user_id
                db.commit()
                db.refresh(row)
                return row.attempts
            except SQLAlchemyError:
                db.rollback()
                raise

    # Próbálkozás számláló nullázása sikeres belépés után
    def reset_for_success(self, pending_token_key: str, user_id: int, ip: str | None, *, actor_user_id: int) -> None:
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
