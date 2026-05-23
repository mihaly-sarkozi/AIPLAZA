# backend/core/modules/auth/repository/persistence/two_factor_repository.py
# Feladat: Emailes 2FA kódok tenant-séma perzisztencia adaptere. Új kódot hashként ment, valid és le nem járt kódot keres, user korábbi kódjait érvényteleníti és kódot used állapotba tesz. Auth repository réteg a TwoFactorService számára.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations
from sqlalchemy.exc import SQLAlchemyError

from shared.utils import normalize_utc_datetime
from core.modules.auth.domain.dto.two_factor_code import TwoFactorCode
from core.modules.auth.models.two_factor_code_orm import TwoFactorCodeORM
from core.kernel.runtime.clock import Clock, SystemClock
from shared.utils.hash import sha256_hex


class TwoFactorRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory, clock: Clock | None = None):
        self._sf = session_factory
        self._clock = clock or SystemClock()

    # OTP kód létrehozása
    def create(self, code: TwoFactorCode, *, created_by: int | None = None) -> TwoFactorCode:
        with self._sf() as db:
            try:
                row = TwoFactorCodeORM(
                    user_id=code.user_id,
                    created_by=created_by if created_by is not None else code.user_id,
                    updated_by=created_by if created_by is not None else code.user_id,
                    code_hash=sha256_hex(code.code),
                    email=code.email,
                    expires_at=code.expires_at,
                    used=code.used
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return code.persisted(
                    id=row.id,
                    created_at=normalize_utc_datetime(row.created_at)
                )
            except SQLAlchemyError:
                db.rollback()
                raise

    # Érvényes OTP kód lekérése
    def get_valid_code(self, user_id: int, code: str) -> TwoFactorCode | None:
        code_hash = sha256_hex(code)
        now = self._clock.now()
        with self._sf() as db:
            row = db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.user_id == user_id,
                TwoFactorCodeORM.code_hash == code_hash,
                TwoFactorCodeORM.used.is_(False),
                TwoFactorCodeORM.expires_at > now,
            ).first()
            if not row:
                return None
            return TwoFactorCode(
                id=row.id,
                user_id=row.user_id,
                code="",  # nyers kód nincs tárolva
                email=row.email,
                expires_at=normalize_utc_datetime(row.expires_at),
                used=row.used,
                created_at=normalize_utc_datetime(row.created_at)
            )

    # Minden OTP kód visszavonása userhez
    def invalidate_user_codes(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.user_id == user_id,
                TwoFactorCodeORM.used == False
            ).update({"used": True, "updated_by": updated_by if updated_by is not None else user_id}, synchronize_session=False)
            db.commit()

    # OTP kód használatának jelölése
    def mark_as_used(self, code_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            db.query(TwoFactorCodeORM).filter(
                TwoFactorCodeORM.id == code_id
            ).update({"used": True, "updated_by": updated_by}, synchronize_session=False)
            db.commit()
