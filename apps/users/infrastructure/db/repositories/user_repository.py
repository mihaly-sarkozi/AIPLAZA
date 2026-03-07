# apps/users/infrastructure/db/repositories/user_repository.py
# User repository (CRUD, list, exists_owner, get_owner, get_by_email)
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from datetime import timezone
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from apps.users.infrastructure.db.models import UserORM
from apps.users.domain.user import User
from apps.users.ports import UserRepositoryInterface


class UserRepository(UserRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    @staticmethod
    def _normalize_dt(dt):  
        """Időzóna normalizálás (UTC)."""
        if dt and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def get_by_id(self, user_id: int) -> User | None:
        """User lekérdezése azonosító alapján."""
        with self._sf() as db:
            row = db.get(UserORM, user_id)
            if not row:
                return None
            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=getattr(row, "role", "user"),
                created_at=self._normalize_dt(row.created_at),
                name=getattr(row, "name", None),
                registration_completed_at=self._normalize_dt(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
                failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                preferred_locale=getattr(row, "preferred_locale", None),
                preferred_theme=getattr(row, "preferred_theme", None),
            )

    def exists_owner(self) -> bool:
        """Van-e már owner a tenantben (az első regisztrált lesz owner)."""
        with self._sf() as db:
            return db.query(UserORM).filter(UserORM.role == "owner").limit(1).first() is not None

    def get_owner(self) -> User | None:
        """Tenant owner (egyetlen); alapértelmezett locale/theme forrája."""
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.role == "owner").limit(1).first()
            if not row:
                return None
            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=getattr(row, "role", "user"),
                created_at=self._normalize_dt(row.created_at),
                name=getattr(row, "name", None),
                registration_completed_at=self._normalize_dt(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
                failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                preferred_locale=getattr(row, "preferred_locale", None),
                preferred_theme=getattr(row, "preferred_theme", None),
            )

    def get_by_email(self, email: str) -> User | None:
        """User lekérdezése email alapján."""
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.email == email).first()
            if not row:
                return None
            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=getattr(row, "role", "user"),
                created_at=self._normalize_dt(row.created_at),
                name=getattr(row, "name", None),
                registration_completed_at=self._normalize_dt(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
                failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                preferred_locale=getattr(row, "preferred_locale", None),
                preferred_theme=getattr(row, "preferred_theme", None),
            )

    def list_all(self) -> list[User]:
        """Minden user listázása."""
        with self._sf() as db:
            rows = db.query(UserORM).order_by(UserORM.created_at.desc()).all()
            def _reg_dt(r):
                v = getattr(r, "registration_completed_at", None)
                return self._normalize_dt(v) if v else None
            return [
                User(
                    id=row.id,
                    email=row.email,
                    password_hash=row.password_hash,
                    is_active=row.is_active,
                    role=getattr(row, "role", "user"),
                    created_at=self._normalize_dt(row.created_at),
                    name=getattr(row, "name", None),
                    registration_completed_at=_reg_dt(row),
                    failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                    preferred_locale=getattr(row, "preferred_locale", None),
                    preferred_theme=getattr(row, "preferred_theme", None),
                )
                for row in rows
            ]

    def create(self, user: User) -> User:
        """User létrehozása."""
        with self._sf() as db:
            try:
                row = UserORM(
                    email=user.email,
                    name=user.name,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    role=user.role,
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
        """User módosítása."""
        with self._sf() as db:
            try:
                row = db.get(UserORM, user.id)
                if not row:
                    raise ValueError(f"User not found: {user.id}")
                row.email = user.email
                row.is_active = user.is_active
                row.role = user.role
                if hasattr(row, "name"):
                    row.name = user.name
                if hasattr(row, "registration_completed_at") and getattr(user, "registration_completed_at", None) is not None:
                    row.registration_completed_at = user.registration_completed_at
                if hasattr(row, "failed_login_attempts"):
                    row.failed_login_attempts = getattr(user, "failed_login_attempts", 0)
                if hasattr(row, "preferred_locale"):
                    row.preferred_locale = getattr(user, "preferred_locale", None)
                if hasattr(row, "preferred_theme"):
                    row.preferred_theme = getattr(user, "preferred_theme", None)
                db.commit()
                db.refresh(row)
                return User(
                    id=row.id,
                    email=row.email,
                    password_hash=row.password_hash,
                    is_active=row.is_active,
                    role=getattr(row, "role", "user"),
                    created_at=self._normalize_dt(row.created_at),
                    name=getattr(row, "name", None),
                    registration_completed_at=self._normalize_dt(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
                    failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                    preferred_locale=getattr(row, "preferred_locale", None),
                    preferred_theme=getattr(row, "preferred_theme", None),
                )
            except SQLAlchemyError:
                db.rollback()
                raise

    def record_failed_login(self, user_id: int) -> None:
        """Sikertelen bejelentkezés: növeli a számlálót; ha >= 5 és nem superuser, is_active=False."""
        user = self.get_by_id(user_id)
        if not user:
            return
        new_count = getattr(user, "failed_login_attempts", 0) + 1
        if new_count >= 5 and not user.is_owner:
            updated = user.with_updates(failed_login_attempts=0, is_active=False)
        else:
            updated = user.with_updates(failed_login_attempts=new_count)
        self.update(updated)

    def reset_failed_login(self, user_id: int) -> None:
        """Sikeres bejelentkezés vagy jelszó beállítás: failed_login_attempts = 0."""
        user = self.get_by_id(user_id)
        if not user:
            return
        self.update(user.with_updates(failed_login_attempts=0))

    def update_password(self, user_id: int, password_hash: str) -> None:
        """Jelszó frissítése."""
        with self._sf() as db:
            try:
                row = db.get(UserORM, user_id)
                if not row:
                    raise ValueError(f"User not found: {user_id}")
                row.password_hash = password_hash
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    def delete(self, user_id: int) -> None:
        """User törlése."""
        with self._sf() as db:
            try:
                row = db.get(UserORM, user_id)
                if not row:
                    raise ValueError(f"User not found: {user_id}")
                # FK-k miatt (ugyanabban a tenant sémában): hivatkozások nullázva/törölve, majd user törlése
                db.execute(text("UPDATE audit_log SET user_id = NULL WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("UPDATE settings SET updated_by = NULL WHERE updated_by = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM user_invite_tokens WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM pending_2fa_logins WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM two_factor_codes WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM refresh_tokens WHERE user_id = :uid"), {"uid": user_id})
                db.delete(row)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise
