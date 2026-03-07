# apps/users/infrastructure/db/repositories/invite_token_repository.py
# Jelszó beállító link tokenek (admin user létrehozás után, 24h érvényes)
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.users.infrastructure.db.models import UserInviteTokenORM
from apps.users.ports.invite_token_repository_interface import (
    InviteTokenRepositoryInterface,
    InviteTokenRecord,
)


class InviteTokenRepository(InviteTokenRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):
        """Időzóna normalizálás (UTC)."""
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def create(self, user_id: int, token_hash: str, expires_at) -> int:
        """Meghívó token létrehozása."""
        with self._sf() as db:
            try:
                row = UserInviteTokenORM(
                    user_id=user_id,
                    token_hash=token_hash,
                    expires_at=expires_at,
                    used_at=None,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return row.id
            except SQLAlchemyError:
                db.rollback()
                raise

    def get_by_token_hash(self, token_hash: str) -> InviteTokenRecord | None:
        """Meghívó token lekérdezése a hash alapján."""
        with self._sf() as db:
            row = db.query(UserInviteTokenORM).filter(
                UserInviteTokenORM.token_hash == token_hash
            ).first()
            if not row:
                return None
            return InviteTokenRecord(
                id=row.id,
                user_id=row.user_id,
                expires_at=self._normalize_dt(row.expires_at),
                used_at=self._normalize_dt(row.used_at) if row.used_at else None,
            )

    def mark_used(self, token_id: int) -> None: 
        """Meghívó token használatának jelzése."""
        with self._sf() as db:
            try:
                row = db.get(UserInviteTokenORM, token_id)
                if not row:
                    return
                row.used_at = datetime.now(timezone.utc)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    def invalidate_all_for_user(self, user_id: int) -> None:    
        """A user összes meghívó tokenjét érvényteleníteti (mindig csak egy élő link legyen)."""
        with self._sf() as db:
            try:
                now = datetime.now(timezone.utc)
                db.query(UserInviteTokenORM).filter(
                    UserInviteTokenORM.user_id == user_id,
                    UserInviteTokenORM.used_at.is_(None),
                ).update({UserInviteTokenORM.used_at: now}, synchronize_session=False)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    def get_user_ids_with_used_token(self) -> set[int]:
        """Azon user_id-k, akiknek van már használt (regisztrációt teljesítő) meghívó tokenje."""
        with self._sf() as db:
            from sqlalchemy import select
            rows = db.execute(
                select(UserInviteTokenORM.user_id)
                .where(UserInviteTokenORM.used_at.isnot(None))
                .distinct()
            ).scalars().all()
            return set(rows) if rows else set()
