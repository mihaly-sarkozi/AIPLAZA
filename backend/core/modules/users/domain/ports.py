# backend/core/modules/users/domain/ports.py
# Feladat: A users modul service portjait definiálja. User repository, billing/training status és kapcsolódó adapter szerződéseket rögzít, hogy a service réteg ne konkrét implementációkra épüljön. Users contract réteg.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Protocol

from core.modules.users.domain.dto import User


class UserRepositoryPort(Protocol):
    def list_all(self) -> list[User]:
        ...

    def get_by_id(self, user_id: int) -> User | None:
        ...

    def get_by_email(self, email: str) -> User | None:
        ...

    def get_by_pending_email_token_hash(self, token_hash: str) -> User | None:
        ...

    def get_owner(self) -> User | None:
        ...

    def exists_owner(self) -> bool:
        ...

    def create(self, user: User, *, created_by: int | None = None) -> User:
        ...

    def update(self, user: User, *, updated_by: int | None = None) -> User:
        ...

    def update_password(self, user_id: int, password_hash: str, *, updated_by: int | None = None) -> None:
        ...

    def reset_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...

    def increment_security_version(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...

    def delete(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...

    def record_failed_login(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...


class InviteTokenRepositoryPort(Protocol):
    def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at,
        *,
        created_by: int | None = None,
        updated_by: int | None = None,
    ) -> None:
        ...

    def invalidate_all_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...


class SessionRepositoryPort(Protocol):
    def invalidate_all_for_user(self, user_id: int, *, updated_by: int | None = None) -> None:
        ...


class UserEmailPort(Protocol):
    def send_set_password_invite(self, to_email: str, set_password_link: str, lang: str | None = None) -> bool:
        ...

    def send_email_change_confirmation(
        self,
        to_email: str,
        confirm_email_link: str,
        *,
        current_email: str,
        new_email: str,
        lang: str | None = None,
    ) -> bool:
        ...

    def send_demo_login_link(self, to_email: str, login_link: str, *, demo_expires_at) -> bool:
        ...

    def send_demo_set_password_invite(self, to_email: str, set_password_link: str, *, demo_expires_at, lang: str | None = None) -> bool:
        ...


class BillingTrainingStatusPort(Protocol):
    def tenant_has_training_material(self, tenant) -> bool:
        ...
