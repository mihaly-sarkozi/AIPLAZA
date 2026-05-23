# backend/core/modules/auth/domain/ports.py
# Feladat: Az auth use case-ek által elvárt repository, token, settings és security logger portokat definiálja. Ezekkel a login, refresh és logout service-ek nem konkrét perzisztencia implementációhoz, hanem stabil interfészhez kötődnek. Auth domain contract réteg a use case-ek és adapterek között.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from core.modules.auth.domain.dto.session import Session
from core.modules.users.domain.dto import User


class TwoFactorSettingsReader(ABC):
    # Ez a metódus a(z) is_two_factor_enabled logikáját valósítja meg.
    @abstractmethod
    def is_two_factor_enabled(self) -> bool:
        ...


class DefaultTwoFactorSettingsReader(TwoFactorSettingsReader):
    # Ez a metódus a(z) is_two_factor_enabled logikáját valósítja meg.
    def is_two_factor_enabled(self) -> bool:
        return False


class AuthUserRepositoryPort(Protocol):
    def get_by_email(self, email: str) -> User | None:
        ...

    def get_by_id(self, user_id: int) -> User | None:
        ...

    def record_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...

    def reset_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...


class AuthSessionRepositoryPort(Protocol):
    def invalidate_all_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...

    def create(self, session: Session, *, created_by: int | None = None) -> None:
        ...

    def get_by_jti(self, jti: str | None) -> Session | None:
        ...

    def update(self, session: Session, *, updated_by: int | None = None) -> None:
        ...


class PendingTwoFactorRepositoryPort(Protocol):
    def create(self, pending_token: str, user_id: int, expires_at, *, created_by: int | None = None) -> None:
        ...

    def get_user_id(self, pending_token: str) -> int | None:
        ...

    def consume(self, pending_token: str) -> None:
        ...


class TokenServicePort(Protocol):
    def verify(self, token: str) -> dict:
        ...

    def make_refresh_pair(self, user_id: int, *, auto_login: bool = False, user_ver: int = 0, tenant_ver: int = 0) -> tuple[str, dict]:
        ...

    def hash_token(self, token: str) -> str:
        ...

    def make_access(self, user_id: int, *, user_ver: int = 0, tenant_ver: int = 0, role: str = "user") -> tuple[str, str]:
        ...


class SecurityLoggerPort(Protocol):
    def login_invalid_user_attempt(self, email: str, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def login_inactive_user_attempt(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def login_bad_password_attempt(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def login_successful_login(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_expired_token(self, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_invalid_token(self, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_wrong_type(self, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_session_expired(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_unknown_jti(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_reuse_detected(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...

    def refresh_success(self, user_id: int, ip: str | None, ua: str | None, **ctx) -> None:
        ...
