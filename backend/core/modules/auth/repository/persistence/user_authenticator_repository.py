# backend/core/modules/auth/repository/persistence/user_authenticator_repository.py
# Feladat: User authenticator/TOTP beállítások tenant-séma perzisztencia adaptere. Pending secretet hoz létre, secretet aktivál, authenticator állapotot lekér, tilt, illetve enabled és pending secrethez olvasási helperöket ad. Auth repository réteg az authenticator alapú 2FA setuphoz és loginhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime, timezone

from core.modules.auth.models.user_authenticator_orm import UserAuthenticatorORM
from core.kernel.runtime.clock import utc_now
from sqlalchemy.exc import ProgrammingError


class UserAuthenticatorRepository:
    def __init__(self, session_factory):
        self._sf = session_factory

    def get_by_user_id(self, user_id: int) -> UserAuthenticatorORM | None:
        with self._sf() as db:
            try:
                return db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            except ProgrammingError as exc:
                message = str(exc).lower()
                if "does not exist" in message and "user_authenticators" in message:
                    # Backward-compatible read path for tenants where MFA table is not provisioned yet.
                    return None
                raise

    def upsert_pending_secret(
        self,
        user_id: int,
        *,
        pending_secret_base32: str,
        pending_expires_at: datetime,
        updated_by: int | None = None,
    ) -> UserAuthenticatorORM:
        with self._sf() as db:
            row = db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            if row is None:
                row = UserAuthenticatorORM(
                    user_id=user_id,
                    is_enabled=False,
                    pending_secret_base32=pending_secret_base32,
                    pending_expires_at=pending_expires_at,
                    created_by=updated_by if updated_by is not None else user_id,
                    updated_by=updated_by if updated_by is not None else user_id,
                )
                db.add(row)
            else:
                row.pending_secret_base32 = pending_secret_base32
                row.pending_expires_at = pending_expires_at
                row.updated_by = updated_by if updated_by is not None else user_id
            db.commit()
            db.refresh(row)
            return row

    def enable_secret(self, user_id: int, *, secret_base32: str, updated_by: int | None = None) -> UserAuthenticatorORM:
        with self._sf() as db:
            row = db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            if row is None:
                row = UserAuthenticatorORM(
                    user_id=user_id,
                    secret_base32=secret_base32,
                    is_enabled=True,
                    pending_secret_base32=None,
                    pending_expires_at=None,
                    created_by=updated_by if updated_by is not None else user_id,
                    updated_by=updated_by if updated_by is not None else user_id,
                )
                db.add(row)
            else:
                row.secret_base32 = secret_base32
                row.is_enabled = True
                row.pending_secret_base32 = None
                row.pending_expires_at = None
                row.updated_by = updated_by if updated_by is not None else user_id
            db.commit()
            db.refresh(row)
            return row

    def disable(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            row = db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            if row is None:
                return
            row.secret_base32 = None
            row.is_enabled = False
            row.pending_secret_base32 = None
            row.pending_expires_at = None
            row.updated_by = updated_by if updated_by is not None else user_id
            db.commit()

    def get_enabled_secret(self, user_id: int) -> str | None:
        with self._sf() as db:
            row = db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            if not row or not row.is_enabled:
                return None
            return (row.secret_base32 or "").strip() or None

    def get_pending_secret(self, user_id: int) -> str | None:
        with self._sf() as db:
            row = db.query(UserAuthenticatorORM).filter(UserAuthenticatorORM.user_id == user_id).first()
            if not row:
                return None
            if not row.pending_secret_base32:
                return None
            pending_expires_at = self._as_utc_aware(row.pending_expires_at)
            if pending_expires_at is None or pending_expires_at <= utc_now():
                return None
            return row.pending_secret_base32

    @staticmethod
    def _as_utc_aware(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
