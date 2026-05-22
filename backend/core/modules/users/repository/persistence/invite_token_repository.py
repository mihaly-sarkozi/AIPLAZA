# backend/core/modules/users/repository/persistence/invite_token_repository.py
# Feladat: A user invite token SQLAlchemy repository adaptere. Token hash alapján olvas, létrehoz, felhasználtnak jelöl és userhez kapcsolt aktív tokeneket kezel. Users invite persistence réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from shared.utils import normalize_utc_datetime
from core.modules.users.domain.dto import InviteToken
from core.modules.users.models.user_invite_token_orm import UserInviteTokenORM


class InviteTokenRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory):
        self._sf = session_factory

    # Meghívó token létrehozása
    def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at,
        *,
        created_by: int | None = None,
        updated_by: int | None = None,
    ) -> int:
        with self._sf() as db:
            try:
                row = UserInviteTokenORM(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    used_at=None,
                    created_by=created_by,
                    updated_by=updated_by if updated_by is not None else created_by,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return row.id
            except SQLAlchemyError:
                db.rollback()
                raise

    # Meghívó token lekérése token hash alapján
    def get_by_token_hash(self, token_hash: str) -> InviteToken | None:
        with self._sf() as db:
            row = db.query(UserInviteTokenORM).filter(UserInviteTokenORM.token_hash == token_hash).first()
            if not row:
                return None
            return InviteToken(
                id=row.id,
                user_id=row.user_id,
                expires_at=normalize_utc_datetime(row.expires_at),
                used_at=normalize_utc_datetime(row.used_at) if row.used_at else None,
                created_at=normalize_utc_datetime(row.created_at) if row.created_at else None,
                created_by=row.created_by,
                updated_at=normalize_utc_datetime(row.updated_at) if row.updated_at else None,
                updated_by=row.updated_by,
            )

    # Meghívó token felhasználása
    def mark_used(self, token_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            try:
                row = db.get(UserInviteTokenORM, token_id)
                if not row:
                    return
                from core.kernel.runtime.clock import utc_now

                row.used_at = utc_now()
                row.updated_by = updated_by
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    # Meghívó tokenek érvénytelenítése userhez
    def invalidate_all_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            try:
                from core.kernel.runtime.clock import utc_now

                now = utc_now()
                db.query(UserInviteTokenORM).filter(
                    UserInviteTokenORM.user_id == user_id,
                    UserInviteTokenORM.used_at.is_(None),
                ).update(
                    {
                        UserInviteTokenORM.used_at: now,
                        UserInviteTokenORM.updated_by: updated_by,
                    },
                    synchronize_session=False,
                )
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise
