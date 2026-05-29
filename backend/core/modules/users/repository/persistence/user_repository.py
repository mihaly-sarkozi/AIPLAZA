# backend/core/modules/users/repository/persistence/user_repository.py
# Feladat: A users tenant-sémás SQLAlchemy repository adaptere. User CRUD, soft delete, PII anonimizálás, password/security mezők, login failure állapot és auth táblák invalidációs műveleteit kezeli. Nagy blast radiusú users persistence réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError

from shared.utils import normalize_utc_datetime
from core.modules.users.domain.dto.user import User
from core.modules.users.models.user_orm import UserORM


class UserRepository:
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(self, session_factory):
        self._sf = session_factory

    # UserORM adatok User DTO-ra konvertálása
    @staticmethod
    def _to_user(row: UserORM) -> User:
        return User(
            id=row.id,
            email=row.email,
            password_hash=row.password_hash,
            is_active=row.is_active,
            role=getattr(row, "role", "user"),
            created_at=normalize_utc_datetime(row.created_at),
            name=getattr(row, "name", None),
            registration_completed_at=normalize_utc_datetime(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
            failed_login_attempts=getattr(row, "failed_login_attempts", 0),
            preferred_locale=getattr(row, "preferred_locale", None),
            preferred_theme=getattr(row, "preferred_theme", None),
            security_version=getattr(row, "security_version", 0),
            credentials_password_set=bool(getattr(row, "credentials_password_set", True)),
            pending_email=getattr(row, "pending_email", None),
            pending_email_token_hash=getattr(row, "pending_email_token_hash", None),
            pending_email_expires_at=normalize_utc_datetime(getattr(row, "pending_email_expires_at", None)) if getattr(row, "pending_email_expires_at", None) else None,
        )

    # User lekérése azonosító alapján
    def get_by_id(self, user_id: int) -> User | None:
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.id == user_id, UserORM.deleted_at.is_(None)).first()
            if not row:
                return None
            return self._to_user(row)

    # Owner létezésének ellenőrzése
    def exists_owner(self) -> bool:
        with self._sf() as db:
            return db.query(UserORM).filter(UserORM.role == "owner", UserORM.deleted_at.is_(None)).limit(1).first() is not None

    # Owner lekérése
    def get_owner(self) -> User | None:
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.role == "owner", UserORM.deleted_at.is_(None)).limit(1).first()
            if not row:
                return None
            return self._to_user(row)

    # User lekérése email alapján
    def get_by_email(self, email: str) -> User | None:
        with self._sf() as db:
            normalized_email = email.strip().lower()
            row = db.query(UserORM).filter(func.lower(UserORM.email) == normalized_email, UserORM.deleted_at.is_(None)).first()
            if not row:
                return None
            return self._to_user(row)

    def get_by_pending_email_token_hash(self, token_hash: str) -> User | None:
        with self._sf() as db:
            row = db.query(UserORM).filter(UserORM.pending_email_token_hash == token_hash, UserORM.deleted_at.is_(None)).first()
            if not row:
                return None
            return self._to_user(row)

    # Minden user listázása
    def list_all(self) -> list[User]:
        with self._sf() as db:
            rows = db.query(UserORM).filter(UserORM.deleted_at.is_(None)).order_by(UserORM.created_at.desc()).all()
            return [self._to_user(row) for row in rows]

    # User létrehozása
    def create(self, user: User, *, created_by: int | None = None) -> User:
        with self._sf() as db:
            try:
                row = UserORM(
                    email=user.email,
                    name=user.name,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    role=user.role,
                    registration_completed_at=getattr(user, "registration_completed_at", None),
                    credentials_password_set=bool(getattr(user, "credentials_password_set", False)),
                    created_by=created_by,
                    updated_by=created_by,
                )
                db.add(row)
                db.flush()
                actor_user_id = created_by if created_by is not None else row.id
                row.created_by = actor_user_id
                row.updated_by = actor_user_id
                db.commit()
                db.refresh(row)
                return user.persisted(id=row.id, created_at=normalize_utc_datetime(row.created_at))
            except SQLAlchemyError:
                db.rollback()
                raise

    # User frissítése
    def update(self, user: User, *, updated_by: int | None = None) -> User:
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
                if hasattr(row, "registration_completed_at"):
                    row.registration_completed_at = getattr(user, "registration_completed_at", None)
                if hasattr(row, "failed_login_attempts"):
                    row.failed_login_attempts = getattr(user, "failed_login_attempts", 0)
                if hasattr(row, "preferred_locale"):
                    row.preferred_locale = getattr(user, "preferred_locale", None)
                if hasattr(row, "preferred_theme"):
                    row.preferred_theme = getattr(user, "preferred_theme", None)
                if hasattr(row, "credentials_password_set"):
                    row.credentials_password_set = bool(getattr(user, "credentials_password_set", True))
                if hasattr(row, "pending_email"):
                    row.pending_email = getattr(user, "pending_email", None)
                if hasattr(row, "pending_email_token_hash"):
                    row.pending_email_token_hash = getattr(user, "pending_email_token_hash", None)
                if hasattr(row, "pending_email_expires_at"):
                    row.pending_email_expires_at = getattr(user, "pending_email_expires_at", None)
                if hasattr(row, "updated_by"):
                    row.updated_by = updated_by if updated_by is not None else user.id
                db.commit()
                db.refresh(row)
                return User(
                    id=row.id,
                    email=row.email,
                    password_hash=row.password_hash,
                    is_active=row.is_active,
                    role=getattr(row, "role", "user"),
                    created_at=normalize_utc_datetime(row.created_at),
                    name=getattr(row, "name", None),
                    registration_completed_at=normalize_utc_datetime(getattr(row, "registration_completed_at", None)) if getattr(row, "registration_completed_at", None) else None,
                    failed_login_attempts=getattr(row, "failed_login_attempts", 0),
                    preferred_locale=getattr(row, "preferred_locale", None),
                    preferred_theme=getattr(row, "preferred_theme", None),
                    security_version=getattr(row, "security_version", 0),
                    credentials_password_set=bool(getattr(row, "credentials_password_set", True)),
                    pending_email=getattr(row, "pending_email", None),
                    pending_email_token_hash=getattr(row, "pending_email_token_hash", None),
                    pending_email_expires_at=normalize_utc_datetime(getattr(row, "pending_email_expires_at", None)) if getattr(row, "pending_email_expires_at", None) else None,
                )
            except SQLAlchemyError:
                db.rollback()
                raise

    # User biztonsági verziójának növelése
    def increment_security_version(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            row = db.get(UserORM, user_id)
            if row:
                row.security_version = getattr(row, "security_version", 0) + 1
                if hasattr(row, "updated_by"):
                    row.updated_by = updated_by if updated_by is not None else user_id
                db.commit()

    # Sikertelen belépés rögzítése (zárolási döntés → LoginSecurityPolicy)
    def record_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        from core.modules.users.domain.policies.login_security_policy import LoginSecurityPolicy

        user = self.get_by_id(user_id)
        if not user:
            return
        decision = LoginSecurityPolicy().evaluate_failed_login(user)
        updates: dict = {"failed_login_attempts": decision.new_failed_attempts}
        if decision.should_lock_account:
            updates["is_active"] = False
        self.update(user.with_updates(**updates), updated_by=updated_by if updated_by is not None else user_id)

    # Sikertelen belépés visszaállítása
    def reset_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        user = self.get_by_id(user_id)
        if not user:
            return
        self.update(user.with_updates(failed_login_attempts=0), updated_by=updated_by if updated_by is not None else user_id)

    # Jelszó frissítése
    def update_password(self, user_id: int, password_hash: str, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            try:
                row = db.get(UserORM, user_id)
                if not row:
                    raise ValueError(f"User not found: {user_id}")
                row.password_hash = password_hash
                if hasattr(row, "credentials_password_set"):
                    row.credentials_password_set = True
                if hasattr(row, "updated_by"):
                    row.updated_by = updated_by if updated_by is not None else user_id
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

    # User törlése
    def delete(self, user_id: int, *, updated_by: int | None = None) -> None:
        with self._sf() as db:
            try:
                row = db.get(UserORM, user_id)
                if not row:
                    raise ValueError(f"User not found: {user_id}")
                from core.kernel.runtime.clock import utc_now

                now = utc_now()
                db.execute(
                    text(
                        "UPDATE user_invite_tokens "
                        "SET used_at = COALESCE(used_at, :now), updated_at = :now, updated_by = :updated_by "
                        "WHERE user_id = :uid"
                    ),
                    {"uid": user_id, "now": now, "updated_by": updated_by if updated_by is not None else user_id},
                )
                db.execute(
                    text(
                        "UPDATE pending_2fa_logins "
                        "SET expires_at = :now "
                        "WHERE user_id = :uid AND expires_at > :now"
                    ),
                    {"uid": user_id, "now": now},
                )
                db.execute(
                    text(
                        "UPDATE two_factor_codes "
                        "SET used = TRUE, updated_at = :now, updated_by = :updated_by "
                        "WHERE user_id = :uid AND used = FALSE"
                    ),
                    {"uid": user_id, "now": now, "updated_by": updated_by if updated_by is not None else user_id},
                )
                db.execute(
                    text(
                        "UPDATE refresh_tokens "
                        "SET valid = FALSE, updated_at = :now, updated_by = :updated_by "
                        "WHERE user_id = :uid AND valid = TRUE"
                    ),
                    {"uid": user_id, "now": now, "updated_by": updated_by if updated_by is not None else user_id},
                )
                row.email = f"deleted-user-{row.id}-{secrets.token_hex(6)}@deleted.local"
                row.name = None
                row.password_hash = secrets.token_urlsafe(32)
                row.is_active = False
                row.role = "user"
                row.registration_completed_at = None
                row.failed_login_attempts = 0
                row.preferred_locale = None
                row.preferred_theme = None
                row.security_version = getattr(row, "security_version", 0) + 1
                row.deleted_at = now
                row.deleted_by = updated_by if updated_by is not None else user_id
                row.updated_by = updated_by if updated_by is not None else user_id
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise
