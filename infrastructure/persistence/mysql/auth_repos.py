from __future__ import annotations

from features.auth.domain.user import User
from features.auth.domain.session import Session as DomSession
from features.auth.ports.repositories import UserRepositoryPort, SessionRepositoryPort
from .auth_models import UserORM, SessionORM


class MySQLUserRepository(UserRepositoryPort):
    def __init__(self, sf):
        self._sf = sf

    def get_by_email(self, email: str):
        with self._sf() as s:
            row = s.query(UserORM).filter(UserORM.email == email).first()
            if not row:
                return None
            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role=row.role,
                created_at=row.created_at,
            )

    def get_by_id(self, user_id: int):
        with self._sf() as s:
            row = s.get(UserORM, user_id)
            if not row:
                return None
            return User(
                id=row.id,
                email=row.email,
                password_hash=row.password_hash,
                is_active=row.is_active,
                role = row.role,
                created_at=row.created_at,
            )


class MySQLSessionRepository(SessionRepositoryPort):
    def __init__(self, sf):
        self._sf = sf

    # --- CREATE ---

    def create(self, s: DomSession) -> DomSession:
        with self._sf() as db:
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
            return s.persisted(id=row.id, created_at=row.created_at)

    # --- GET ---

    def get_by_jti(self, jti: str) -> DomSession | None:
        with self._sf() as db:
            row = db.query(SessionORM).filter(SessionORM.jti == jti).first()
            if not row:
                return None
            return DomSession(
                id=row.id,
                user_id=row.user_id,
                jti=row.jti,
                token_hash=row.token_hash,
                valid=row.valid,
                ip=row.ip,
                user_agent=row.user_agent,
                expires_at=row.expires_at,
                created_at=row.created_at,
            )

    # --- UPDATE (invalidate) ---

    def invalidate(self, jti: str) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.jti == jti).update({"valid": False})
            db.commit()

    def invalidate_all_for_user(self, user_id: int) -> None:
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.user_id == user_id,
                SessionORM.valid.is_(True)
            ).update({"valid": False})
            db.commit()

    def invalidate_by_hash(self, token_hash: str) -> None:
        """Visszavonás token hash alapján (logout / token theft esetén)."""
        with self._sf() as db:
            db.query(SessionORM).filter(
                SessionORM.token_hash == token_hash,
                SessionORM.valid.is_(True)
            ).update({"valid": False})
            db.commit()

    # --- UPDATE (domain invalidate támogatása) ---

    def update(self, s: DomSession) -> DomSession:
        """Session frissítése domain-ből (pl. invalidate vagy refresh után)."""
        with self._sf() as db:
            db.query(SessionORM).filter(SessionORM.id == s.id).update({
                "valid": s.valid,
                "expires_at": s.expires_at,
                "ip": s.ip,
                "user_agent": s.user_agent,
            })
            db.commit()
            return s
