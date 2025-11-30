# apps/auth/infrastructure/db/repositories.py
"""
Megvawlósítja a user repository interface-t
"""
from __future__ import annotations

from datetime import timezone
from sqlalchemy.exc import SQLAlchemyError

from apps.auth.infrastructure.db.models import UserORM, SessionORM
from apps.auth.ports.repositories import UserRepositoryPort, SessionRepositoryPort
from apps.auth.domain.user import User
from apps.auth.domain.session import Session


# -----------------------------------------------------
# USER REPOSITORY
# -----------------------------------------------------

class MySQLUserRepository(UserRepositoryPort):

    def __init__(self, sf):
        self._sf = sf

    # --- HELPER: timezone normalize ---
    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def get_by_id(self, user_id: int) -> User | None:
        with self._sf() as db:
            row = db.get(UserORM, user_id)
            if not row:
                return None

            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=row.role,
                is_superuser=row.is_superuser,
                created_at=self._normalize_dt(row.created_at),
            )
    
    def get_by_email(self, email: str) -> User | None:
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.email == email).first()
            if not row:
                return None

            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=row.role,
                is_superuser=row.is_superuser,
                created_at=self._normalize_dt(row.created_at),
            )
    
    def list_all(self) -> list[User]:
        """Összes user listázása."""
        with self._sf() as db:
            rows = db.query(UserORM).order_by(UserORM.created_at.desc()).all()
            return [
                User(
                    id=row.id,
                    email=row.email,
                    password_hash=row.password_hash,
                    is_active=row.is_active,
                    role=row.role,
                    is_superuser=row.is_superuser,
                    created_at=self._normalize_dt(row.created_at),
                )
                for row in rows
            ]
    
    def create(self, user: User) -> User:
        """Új user létrehozása."""
        with self._sf() as db:
            try:
                row = UserORM(
                    email=user.email,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    role=user.role,
                    is_superuser=user.is_superuser,
                )
                db.add(row)
                db.commit()
                db.refresh(row)
                return user.persisted(
                    id=row.id,
                    created_at=self._normalize_dt(row.created_at)
                )
            except SQLAlchemyError:
                db.rollback()
                raise
    
    def update(self, user: User) -> User:
        """User frissítése."""
        with self._sf() as db:
            try:
                row = db.get(UserORM, user.id)
                if not row:
                    raise ValueError(f"User not found: {user.id}")
                
                row.email = user.email
                row.is_active = user.is_active
                row.role = user.role
                # is_superuser nem módosítható (csak regisztrációkor)
                
                db.commit()
                db.refresh(row)
                return User(
                    id=row.id,
                    email=row.email,
                    password_hash=row.password_hash,
                    is_active=row.is_active,
                    role=row.role,
                    is_superuser=row.is_superuser,
                    created_at=self._normalize_dt(row.created_at),
                )
            except SQLAlchemyError:
                db.rollback()
                raise
    
    def delete(self, user_id: int) -> None:
        """User törlése (superuser nem törölhető)."""
        with self._sf() as db:
            try:
                row = db.get(UserORM, user_id)
                if not row:
                    raise ValueError(f"User not found: {user_id}")
                
                if row.is_superuser:
                    raise ValueError("Superuser cannot be deleted")
                
                db.delete(row)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise


# -----------------------------------------------------
# SESSION REPOSITORY
# -----------------------------------------------------

class MySQLSessionRepository(SessionRepositoryPort):

    def __init__(self, sf):
        self._sf = sf

    @staticmethod
    def _normalize_dt(dt):
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # --- CREATE ---
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

    # --- GET ---
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

    # --- INVALIDATE METHODS ---
    def invalidate(self, jti: str) -> None:
        with self._sf() as db:
            db.query(SessionORM)\
                .filter(SessionORM.jti == jti)\
                .update({"valid": False}, synchronize_session=False)
            db.commit()

    def invalidate_all_for_user(self, user_id: int) -> None:
        with self._sf() as db:
            db.query(SessionORM)\
                .filter(SessionORM.user_id == user_id, SessionORM.valid.is_(True))\
                .update({"valid": False}, synchronize_session=False)
            db.commit()

    def invalidate_by_hash(self, token_hash: str) -> None:
        with self._sf() as db:
            db.query(SessionORM)\
                .filter(SessionORM.token_hash == token_hash, SessionORM.valid.is_(True))\
                .update({"valid": False}, synchronize_session=False)
            db.commit()

    # --- UPDATE FROM DOMAIN ---
    def update(self, s: Session) -> Session:
        with self._sf() as db:
            db.query(SessionORM)\
                .filter(SessionORM.id == s.id)\
                .update({
                    "valid": s.valid,
                    "expires_at": s.expires_at,
                    "ip": s.ip,
                    "user_agent": s.user_agent,
                }, synchronize_session=False)
            db.commit()
            return s
